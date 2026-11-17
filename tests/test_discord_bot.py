"""Offline integration regressions against real Discord component types.

Missing Discord/Airtable dependencies skip collection, not qualification. No
bot login, provider request, Airtable request or real private input is used.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import importlib.util
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pandas as pd
import pytest


discord = pytest.importorskip("discord")
pyairtable = pytest.importorskip("pyairtable")
pytest.importorskip("tqdm")
from discord.ext import commands
import iris_llm


@pytest.fixture
def bot_module(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("import attempted service, credential or private-input I/O")

    name = "iris_test_discord_bot"
    source = Path(__file__).resolve().parents[1] / "discord_bot.py"
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    with monkeypatch.context() as guard:
        for key in ("AIRTABLE_API_KEY", "DISCORD_BOT_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY"):
            guard.delenv(key, raising=False)
        guard.setattr(pyairtable, "Table", forbidden)
        guard.setattr(pd, "read_csv", forbidden)
        guard.setattr(commands.Bot, "run", forbidden)
        for method in ("complete", "chat", "chat_completion"):
            guard.setattr(iris_llm, method, forbidden)
        spec.loader.exec_module(module)
    return module


def test_import_registers_usable_commands_without_service_initialization(bot_module):
    assert bot_module.bot.get_command("ask") is bot_module.iris
    assert bot_module.bot.intents.message_content


def test_frankeniris_offloads_provider_and_keeps_history_ids_and_delivery_on_loop(bot_module, monkeypatch):
    async def scenario():
        loop = asyncio.get_running_loop()
        loop_thread = threading.get_ident()
        entered = asyncio.Event()
        release = threading.Event()
        calls, sent = [], []
        monkeypatch.setattr(bot_module.bot._connection, "user", SimpleNamespace(id=101, name="shared"))

        def complete(*args, **kwargs):
            assert threading.get_ident() != loop_thread
            loop.call_soon_threadsafe(entered.set)
            assert release.wait(5), "event loop failed to progress while provider blocked"
            return "Synthetic relay"

        def chat(messages, **kwargs):
            assert threading.get_ident() != loop_thread
            calls.append(messages)
            return "r" * 4500

        async def history(**kwargs):
            yield SimpleNamespace(author=SimpleNamespace(id=101, name="changed"), content="bot plain", embeds=[])
            yield SimpleNamespace(author=SimpleNamespace(id=101, name="changed"), content="", embeds=[discord.Embed(description="bot embed")])
            yield SimpleNamespace(author=SimpleNamespace(id=202, name="shared"), content="human plain", embeds=[])
            yield SimpleNamespace(author=SimpleNamespace(id=202, name="shared"), content="", embeds=[discord.Embed(description="human embed")])

        async def send(text):
            assert threading.get_ident() == loop_thread
            sent.append(text)

        monkeypatch.setattr(iris_llm, "complete", complete)
        monkeypatch.setattr(iris_llm, "chat", chat)
        message = SimpleNamespace(content="Synthetic question", channel=SimpleNamespace(history=history, send=send))
        task = asyncio.create_task(bot_module.frankeniris(message))
        try:
            await asyncio.wait_for(entered.wait(), 5)
            await asyncio.sleep(0)
            release.set()
            await asyncio.wait_for(task, 10)
        finally:
            release.set()
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        roles = {item["content"]: item["role"] for item in calls[0]}
        assert roles["bot plain"] == roles["bot embed"] == "assistant"
        assert roles["human plain"] == roles["human embed"] == "user"
        assert "".join(sent) == "r" * 4500
        assert [len(text) for text in sent] == [2000, 2000, 500]

    asyncio.run(scenario())


def test_context_trimming_keeps_current_turn_and_only_evicts_necessary_history(bot_module):
    first = {"role": "system", "content": "system"}
    old = {"role": "user", "content": "1234567890"}
    retained = {"role": "assistant", "content": "abc"}
    current = {"role": "user", "content": "final"}
    result = bot_module.trim_context([first, old, retained, current], limit=20)
    assert result == [first, retained, current]
    assert sum(len(item["content"]) for item in result) <= 20


def _interaction(user):
    async def send_message(*args, **kwargs):
        pass

    return SimpleNamespace(user=user, response=SimpleNamespace(send_message=send_message))


@pytest.mark.parametrize("submitted", [True, False])
def test_ask_feedback_uses_actual_contributor_and_timeout_adds_no_row(bot_module, monkeypatch, tmp_path, submitted):
    monkeypatch.chdir(tmp_path)
    original = bot_module.response_view

    async def scenario():
        requester = SimpleNamespace(id=1, name="Requester")
        contributor = SimpleNamespace(id=2, name="Contributor")

        def response_view(**kwargs):
            view, modal = original(**kwargs)

            async def wait():
                if submitted:
                    modal.answer._value = "Synthetic feedback"
                    await modal.on_submit(_interaction(contributor))
                    modal.answer._value = "Duplicate feedback"
                    await modal.on_submit(_interaction(requester))
                else:
                    await view.on_timeout()
                    view.stop()

            modal.wait = wait
            return view, modal

        async def send(*args, **kwargs):
            pass

        monkeypatch.setattr(bot_module, "response_view", response_view)
        monkeypatch.setattr(iris_llm, "complete", lambda *a, **k: "Synthetic response")
        ctx = SimpleNamespace(message=SimpleNamespace(author=requester), send=send)
        await bot_module.iris.callback(ctx, thought="Synthetic prompt")

    asyncio.run(scenario())
    path = tmp_path / "iris_training-data.csv"
    if submitted:
        frame = pd.read_csv(path)
        assert frame["speaker"].tolist() == ["2:Contributor"]
        assert frame["completion"].tolist() == ["Synthetic feedback"]
        assert "Synthetic prompt" in frame.iloc[0]["prompt"]
    else:
        assert not path.exists()


def test_feedback_appends_are_atomic_and_malformed_input_is_not_reset(bot_module, tmp_path):
    path = tmp_path / "feedback.csv"
    pd.DataFrame([{"prompt": "old", "completion": "kept", "speaker": "0:old", "receipt": "preserved"}]).to_csv(path, index=False)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(bot_module.append_training_data, f"p{i}", f"c{i}", f"{i}:user", path) for i in (1, 2)]
        for future in futures:
            future.result(timeout=5)
    frame = pd.read_csv(path)
    assert set(frame["completion"]) == {"kept", "c1", "c2"}
    assert frame.loc[frame["prompt"] == "old", "receipt"].tolist() == ["preserved"]
    path.write_text("wrong,columns\nx,y\n", encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ValueError):
        bot_module.load_training_data(path)
    assert path.read_bytes() == before
    with pytest.raises(ValueError):
        bot_module.append_training_data("p", "c", "3:user", path)
    assert path.read_bytes() == before


def _group(bot_module, monkeypatch, count, submitted):
    people, deliveries = [], {}
    for index in range(count):
        deliveries[index] = []

        async def send(*args, _index=index, **kwargs):
            if "embed" in kwargs:
                deliveries[_index].append(kwargs["embed"])

        people.append(SimpleNamespace(id=index + 10, name=f"person{index}", send=send))
    guild = SimpleNamespace(roles=[SimpleNamespace(name="Birdies", members=people)], members=people)
    monkeypatch.setattr(bot_module.bot, "get_guild", lambda identifier: guild)
    monkeypatch.setattr(bot_module.bot._connection, "_guilds", {1: guild})
    original = bot_module.response_view
    allocated = []

    def response_view(**kwargs):
        index = len(allocated)
        allocated.append(index)
        view, modal = original(**kwargs)

        async def wait():
            if submitted:
                modal.answer._value = chr(ord("A") + index) * 400
                await modal.on_submit(_interaction(people[index]))
            else:
                await view.on_timeout()
                view.stop()

        modal.wait = wait
        return view, modal

    monkeypatch.setattr(bot_module, "response_view", response_view)
    return deliveries


def test_group_summary_sends_distinct_real_chunks_and_bounded_complete_results(bot_module, monkeypatch):
    async def scenario():
        deliveries = _group(bot_module, monkeypatch, 6, True)
        prompts = []

        def complete(prompt, **kwargs):
            prompts.append(prompt)
            return "Consensus " * 700

        async def send(*args, **kwargs):
            pass

        monkeypatch.setattr(iris_llm, "complete", complete)
        ctx = SimpleNamespace(message=SimpleNamespace(author=SimpleNamespace(name="JohnAsh")), send=send)
        await bot_module.ask_group.callback(ctx, question="Synthetic question")
        assert len(prompts) == 2
        assert "A" * 400 in prompts[0] and "A" * 400 not in prompts[1]
        assert "F" * 400 in prompts[1] and "F" * 400 not in prompts[0]
        for embeds in deliveries.values():
            assert all(len(embed.description or "") <= 4000 and len(embed) <= 6000 for embed in embeds)
            answers = "".join(embed.description for embed in embeds if embed.title == "Responses")
            assert answers == "".join(chr(ord("A") + index) * 400 + "\n\n" for index in range(6))
            consensus = "".join(embed.description for embed in embeds if embed.title == "Consensus (beta)")
            assert consensus.count("Consensus ") == 1400

    asyncio.run(scenario())


def test_group_timeouts_never_request_or_deliver_a_fake_consensus(bot_module, monkeypatch):
    async def scenario():
        _group(bot_module, monkeypatch, 2, False)
        sent = []

        async def send(*args, **kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(iris_llm, "complete", lambda *a, **k: pytest.fail("timeout consensus request"))
        ctx = SimpleNamespace(message=SimpleNamespace(author=SimpleNamespace(name="JohnAsh")), send=send)
        await bot_module.ask_group.callback(ctx, question="Synthetic question")
        assert [entry["embed"].title for entry in sent] == ["No Responses"]

    asyncio.run(scenario())


def test_infuse_browser_failure_closes_once_off_loop_without_sending_text(bot_module, monkeypatch):
    async def scenario():
        loop_thread = threading.get_ident()
        closed = []

        def get(url):
            assert threading.get_ident() != loop_thread
            raise RuntimeError("synthetic navigation failure")

        driver = SimpleNamespace(get=get, quit=lambda: closed.append(threading.get_ident()))
        webdriver = SimpleNamespace(
            ChromeOptions=lambda: SimpleNamespace(add_argument=lambda value: None),
            Chrome=lambda **kwargs: driver,
        )
        monkeypatch.setitem(sys.modules, "selenium", SimpleNamespace(webdriver=webdriver))
        monkeypatch.setitem(sys.modules, "bs4", SimpleNamespace(BeautifulSoup=lambda *a: pytest.fail("parse after navigation failure")))
        monkeypatch.setattr(iris_llm, "chat_completion", lambda *a, **k: pytest.fail("provider after navigation failure"))

        async def send(*args, **kwargs):
            pytest.fail("failure produced a fabricated delivery")

        with pytest.raises(RuntimeError, match="navigation"):
            await bot_module.infuse.callback(SimpleNamespace(send=send), link="https://example.invalid/synthetic")
        assert len(closed) == 1
        assert closed[0] != loop_thread

    asyncio.run(scenario())


def test_infuse_null_raw_choice_propagates_canonical_error(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "extract_text_from_url", lambda url: "Synthetic page")
    monkeypatch.setattr(iris_llm, "chat_completion", lambda *a, **k: SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None))]
    ))

    async def send(*args, **kwargs):
        pytest.fail("null model output produced a delivery")

    async def scenario():
        with pytest.raises(iris_llm.ModelOutputError):
            await bot_module.infuse.callback(SimpleNamespace(send=send), link="https://example.invalid/synthetic")

    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["malformed", "unreadable"])
def test_existing_read_failures_preserve_csv_bytes(bot_module, monkeypatch, tmp_path, failure):
    path = tmp_path / "feedback.csv"
    path.write_text('prompt,completion,speaker\n"unterminated\n', encoding="utf-8")
    before = path.read_bytes()
    error = pd.errors.ParserError
    if failure == "unreadable":
        def unreadable(*args, **kwargs):
            raise PermissionError("synthetic permission failure")

        monkeypatch.setattr(bot_module.pd, "read_csv", unreadable)
        error = PermissionError
    with pytest.raises(error):
        bot_module.load_training_data(path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("text", ["", "  \n  "])
def test_infuse_no_text_reports_a_diagnostic_without_a_provider_request(bot_module, monkeypatch, text):
    monkeypatch.setattr(bot_module, "extract_text_from_url", lambda link: text)
    monkeypatch.setattr(iris_llm, "chat_completion", lambda *a, **k: pytest.fail("empty provider request"))

    async def scenario():
        sent = []

        async def send(value):
            sent.append(value)

        await bot_module.infuse.callback(SimpleNamespace(send=send), link="https://example.invalid/synthetic")
        assert len(sent) == 1 and isinstance(sent[0], str) and sent[0].strip()

    asyncio.run(scenario())


def test_bounded_embeds_preserve_all_text_image_and_final_interaction_controls(bot_module):
    async def scenario():
        deliveries = []
        view = discord.ui.View()

        async def send(**kwargs):
            deliveries.append(kwargs)

        text = "Synthetic paragraph. " * 600
        await bot_module.send_embed_text(
            SimpleNamespace(send=send), "Title " * 60, text,
            image_url="https://example.invalid/synthetic.png", view=view,
        )
        assert "".join(item["embed"].description for item in deliveries) == text
        assert all(len(item["embed"].description) <= 4000 and len(item["embed"]) <= 6000 for item in deliveries)
        assert deliveries[0]["embed"].image.url == "https://example.invalid/synthetic.png"
        assert all(item["embed"].image.url is None for item in deliveries[1:])
        assert deliveries[-1]["view"] is view
        assert all(item["view"] is None for item in deliveries[:-1])
        view.stop()

    asyncio.run(scenario())
