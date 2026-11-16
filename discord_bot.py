import os
import re
import sys
import random
import time
import datetime
import dateutil
import tempfile
import threading
from pathlib import Path
from parse_fourthought import clean_text, extract_text_from_url

import iris_llm  # OpenRouter model client (current openai SDK surface)
import discord
import asyncio
import aiohttp
import json

import pandas as pd

from tqdm import tqdm

from discord import app_commands
from discord.utils import get
from pprint import pprint
from pyairtable import Table
from discord.ui import Button, View, TextInput, Modal
from discord.ext import commands

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)
airtable = None
tarot_lookup = {}
_training_lock = threading.Lock()


def setup_integrations():
	"""Perform service/private-input initialization only at explicit startup."""
	global airtable, tarot_lookup
	airtable = Table(os.environ["AIRTABLE_API_KEY"], 'app2X00KuiIxPwGsf', 'cards')
	try:
		records = [record for page in airtable.iterate() for record in page]
		tarot_lookup = {
			record['fields']['Card Name']: record['fields'].get('Short Description', '')
			for record in records
		}
	except Exception:
		frame = pd.read_csv('tarot_text.csv')
		tarot_lookup = dict(zip(frame['card_name'], frame['text']))


async def complete_async(*args, **kwargs):
	return await asyncio.to_thread(iris_llm.complete, *args, **kwargs)


async def chat_async(*args, **kwargs):
	return await asyncio.to_thread(iris_llm.chat, *args, **kwargs)


async def chat_completion_async(*args, **kwargs):
	return await asyncio.to_thread(iris_llm.chat_completion, *args, **kwargs)


async def send_embed_text(target, title, text, *, image_url=None, view=None):
	"""Deliver all text, attaching an image first and interactive controls last."""
	for offset in range(0, len(text), 4000):
		embed = discord.Embed(title=title[:256], description=text[offset:offset + 4000])
		if image_url and offset == 0:
			embed.set_image(url=image_url)
		await target.send(embed=embed, view=view if offset + 4000 >= len(text) else None)


def trim_context(conversation, limit=20000):
	total = sum(len(message["content"]) for message in conversation)
	while total > limit and len(conversation) > 2:
		total -= len(conversation.pop(1)["content"])
	return conversation


def group_prompts(question, answers, chunk_length=1750):
	if chunk_length < 1:
		raise ValueError("chunk_length must be positive")
	return [pool_prompt(question, answers[index:index + chunk_length]) for index in range(0, len(answers), chunk_length)]


def _write_training_frame(frame, path):
	path = Path(path)
	temporary = None
	try:
		with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
			temporary = Path(handle.name)
			frame.to_csv(handle, index=False)
		temporary.replace(path)
	finally:
		if temporary is not None:
			temporary.unlink(missing_ok=True)


def _read_training_frame(path):
	try:
		frame = pd.read_csv(path)
	except FileNotFoundError:
		return pd.DataFrame(columns=['prompt', 'completion', 'speaker'])
	if not {'prompt', 'completion', 'speaker'}.issubset(frame.columns):
		raise ValueError("Training CSV requires prompt, completion and speaker columns")
	return frame


def append_training_data(prompt, completion, speaker, path='iris_training-data.csv'):
	global training_data
	with _training_lock:
		frame = _read_training_frame(path)
		row = {"prompt": prompt, "completion": completion, "speaker": speaker}
		updated = pd.concat([frame, pd.DataFrame([row])], ignore_index=True)
		_write_training_frame(updated, path)
		training_data = updated


def card_image(card_name):
	if airtable is None:
		raise RuntimeError("Airtable is not initialized")
	for page in airtable.iterate():
		for record in page:
			fields = record["fields"]
			if fields["Card Name"] == card_name and fields.get("All images"):
				return fields["All images"][0]["url"]
	return ""

training_data = ""

# Fine-tuned davinci models are retired; the slots map to catalog-verified
# OpenRouter chat models (checked by scripts/check_openrouter_models.py).
models = {
	"living": "openai/gpt-4o-mini",
	"osiris": "openai/gpt-4o-mini",
	"2020": "openai/gpt-4o-mini",
	"purple": "openai/gpt-4o-mini",
	"semantic": "openai/gpt-4o-mini",
	"davinci": "openai/gpt-4o-mini",
	"chat-iris": "openai/gpt-4o",
	"chat-iris-b": "openai/gpt-4o-mini",
	"chat-iris-a": "openai/gpt-4o-mini",
	"chat-iris-0": "openai/gpt-4o-mini"
}

people = []

class AskModal(Modal, title="Ask Modal"):

	answer = TextInput(label="Answer", max_length=400, style=discord.TextStyle.long)

	def add_view(self, question, view: View):
		self.answer.placeholder = question[0:100]
		self.view = view
		self.submission = None

	async def on_submit(self, interaction: discord.Interaction):
		if self.submission is not None:
			await interaction.response.send_message("Response already submitted.", ephemeral=True)
			return
		value = str(self.answer.value)
		self.submission = (interaction.user.id, interaction.user.name, value)
		embed = discord.Embed(title="Your Response", description=value)
		embed.set_author(name=str(interaction.user))
		try:
			await interaction.response.send_message(embed=embed)
		finally:
			self.view.stop()
			self.stop()

def response_view(modal_text="default text", modal_label="Response", button_label="Answer"):	

	async def view_timeout():
		modal.stop()	

	view = View()
	view.on_timeout = view_timeout
	view.timeout = 2700.0
	view.auto_defer = True

	modal = AskModal(title=modal_label)
	modal.auto_defer = True
	modal.timeout = 2700.0

	async def button_callback(interaction):
		answer = await interaction.response.send_modal(modal)

	button = Button(label=button_label, style=discord.ButtonStyle.blurple)
	button.callback = button_callback
	view.add_item(button)
	modal.add_view(modal_text, view)

	return view, modal

def group_share(thought="thought", prompt="", prompter="latent space"):

	channel = bot.get_channel(1022572367244967979)

	async def button_callback(interaction):
		await interaction.response.defer()
		await send_embed_text(channel, "Seeds of Wisdom", f"{thought}\n\n**Gardener**\n{prompter}")

	button = Button(label="share", style=discord.ButtonStyle.blurple)
	button.callback = button_callback

	return button

def elaborate(ctx, prompt="prompt"):

	global models

	e_prompt = prompt + ". \n\n More thoughts in detail below. \n\n"

	button = Button(label="elaborate", style=discord.ButtonStyle.blurple)

	async def button_callback(interaction):

		if button.disabled:
			return

		button.disabled = True
		await interaction.response.defer()

		response_text = await complete_async(
			e_prompt, model=models["semantic"], temperature=0.11, max_tokens=222,
			top_p=1, frequency_penalty=1, presence_penalty=1, stop=["END"],
		)


		response_text = response_text.replace("###", "").strip()

		await send_embed_text(ctx, "Elaboration (beta)", f"**Prompt**\n{prompt}\n\n**Elaboration**\n{response_text}")


	button.callback = button_callback

	return button

def redo_view(ctx, prompt, question):

	async def button_callback(interaction):

		await interaction.response.defer()

		response_text = await complete_async(
			prompt, model="openai/gpt-4o-mini", temperature=1, max_tokens=222,
			top_p=1, frequency_penalty=2, presence_penalty=2, stop=["END"],
		)
		await send_embed_text(ctx, "Consensus", f"**Question**\n{question}\n\n**Consensus**\n{response_text}")

	view = View()
	view.timeout = None
	button = Button(label="Redo", style=discord.ButtonStyle.blurple)
	button.callback = button_callback
	view.add_item(button)

	return view

def load_training_data(path='iris_training-data.csv'):
	global training_data
	with _training_lock:
		frame = _read_training_frame(path)
		if not Path(path).exists():
			_write_training_frame(frame, path)
		training_data = frame
		return frame

def members(debug=False):

	members = []
	testers = ["John Ash's Username for Discord", "JohnAsh", "EveInTheGarden"]
	global people

	if debug:
		for guild in bot.guilds:
			for member in guild.members:
				if member.name in testers:
					members.append(member)
	else:
		for guild in bot.guilds:
			for member in guild.members:
				if member.name != "Hidden Iris":
					members.append(member)

	unique_members = [*set(members)]
	people = unique_members

def make_prompt(question, joined_answers):

	prompt = question + "\n\nAnswers are below"
	prompt += "\n\nWrite a long detail paragraph summarizing and analyzing the answers below. What are the commonalities and differences in the answers? Are there any outliers?"
	prompt += "\n\n---\n\nAnswers:\n\n" + joined_answers
	prompt += "---\n\nThe question was: " + question + "\n\n"
	prompt += "Write a long detailed paragraph about the question as if you were a singular voice formed from all of the views above. What does this community believe?"
	prompt += "\n\nSum the answers into one answer that best represents all the views shared. If many questions are provided respond with a question representing what most people are uncertain about"
	prompt += "\n\n"

	return prompt

def pool_prompt(question, joined_answers):

	prompt = question + "\n\nAnswers are below"
	prompt += "\n\nPool all of the answers into a single response or question"
	prompt += "\n\n---\n\nAnswers:\n\n" + joined_answers
	prompt += "---\n\nThe question was: " + question + "\n\n"
	prompt += "Pool all of the answers into a single response or question that reflects the views of all the responders. Also write a long detailed paragraph extrapolating on the thoughts above"
	prompt += "\n\n"

	return prompt

def chunk_text(text, chunk_length=1000):
	if chunk_length < 1:
		raise ValueError("chunk_length must be positive")
	text = clean_text(text)
	return [text[index:index + chunk_length] for index in range(0, len(text), chunk_length)]

async def interpretation(ctx, prompt):

    text = await complete_async(
        prompt, model=models["semantic"], temperature=0.8, max_tokens=222,
        top_p=1, frequency_penalty=2, presence_penalty=2, stop=["END"],
    )
    view, modal = response_view(modal_text="Write your feedback here", modal_label="Feedback", button_label="Send Feedback")
    view.add_item(group_share(thought=text, prompter=ctx.message.author.name))
    view.add_item(elaborate(ctx, prompt=text))
    await send_embed_text(ctx, "Interpretation", text, view=view)

def one_shot(content):
	return iris_llm.complete(
		content, model=models["chat-iris"], temperature=0.9, max_tokens=222,
		top_p=1, frequency_penalty=1.5, presence_penalty=1.5, stop=["END"],
	).replace("###", "").strip()

async def question_pool(message):

	channel = bot.get_channel(1086437563654475846)
	summary_count = 0

	# Load Chat Context
	messages = []

	# Ignore Slash Commands
	last_message = [message async for message in channel.history(limit=1)][0]
	if last_message.content.startswith("/"):
		return

	#iris_answer = one_shot(last_message)

	# print(iris_answer)

	async for hist in channel.history(limit=50):
		if not hist.content.startswith('/'):
			if hist.author == bot.user: 
				summary_count += 1
				if summary_count < 1:
					messages.append((hist.author, hist.content))
			else:
				messages.append((hist.author, hist.content))
			if len(messages) == 15:
				break

	messages.reverse()

	conversation = [{"role": "system", "content": "You are a question summarizer Iris. You are summarizing a thread of questions about Cognicism and related concepts. You ignore everything except questions. People will ask you various questions about cognicism and you job is to summarize what people want to know"}]

	for m in messages:
		if  m[0].id == bot.user.id:
			conversation.append({"role": "assistant", "content": m[1]})
		else:
			conversation.append({"role": "user", "content": m[1]})

	conversation.append({"role": "system", "content": "You have been moderating a running thread of questions about cognicism. Your job is to help summarize these questions and NOT to answer them"})
	conversation.append({"role": "system", "content": "My primary job is to summarize what people are uncertain about. I will summarize peoples questions and that is it. I will vary my output but keep them focused on what people don't know and keep it 250 words long"})
	conversation.append({"role": "assistant", "content": "I NEVER answer questions. I summarize questions and communal uncentainty. I ignore anything that doesn't end in a question mark. I will keep my summary very short or about 250 words long"})

	response = await chat_async(conversation, model="openai/gpt-4o-mini")

	# Split response into chunks if longer than 2000 characters
	if len(response) > 2000:
		for chunk in [response[i:i+2000] for i in range(0, len(response), 2000)]:
			await message.channel.send(chunk)
	else:
		await message.channel.send(response)

async def fourthought_pool(message):

	channel = bot.get_channel(1090373822454182090)
	summary_count = 0

	# Load Chat Context
	messages = []

	# Ignore Slash Commands
	last_message = [message async for message in channel.history(limit=1)][0]
	if last_message.content.startswith("/"):
		return

	async for hist in channel.history(limit=50):
		if not hist.content.startswith('/'):
			if hist.author == bot.user: 
				summary_count += 1
				if summary_count < 1:
					messages.append((hist.author, hist.content))
			else:
				messages.append((hist.author, hist.content))
			if len(messages) == 9:
				break

	messages.reverse()

	if messages[-1][1].startswith("Iris,"):

		conversation = [
			{"role": "system", "content": "You are Iris, an AI language model assisting people in a Discord channel. Your main function is to help be a time compass and guide people through time. You're an oracle that helps people focus on the future but an oracle that also looks back to help guide that focus. In this case we want you to follow the speaker's instruction very closely"},
			{"role": "system", "content": "Follow the most recent speakers's instructions as closely as possible in the context of the thread so far"}
		]

	else:

		conversation = [
			{"role": "system", "content": "You are Iris, an AI language model assisting people in a Discord channel. Your main function is to help be a time compass and guide people through time. You're an oracle that helps people focus on the future but an oracle that also looks back to help guide that focus"},
			{"role": "system", "content": "The FourThought dialectic consists of four thought types based on temporal focus and uncertainty: Statements, Predictions, Reflections, and Questions. Guide people to contribute to achieve their goals through time by helping them become better predictors and have better insight and hindsight"},
			{"role": "system", "content": "While people communicate in this dialectic, your role is to be the storyteller, weaving together these different perceptions into a narrative that helps them to work together towards these goals. You elevate and praise and form synthesis for good work that heals the planet and the community"},
			{"role": "system", "content": "Users may provide valence (good) and certainty (truth) scores to help evaluate the quality and relevance of the contributions. Use these scores to prioritize and weigh the information provided by people. Certainty (0 - 100%) evaluates whether a thought aligns with one's sense of reality (false to true, with uncertainty in the middle), while valence evaluates whether a thought aligns with one's sense of morality (bad to good, with neutrality in the center)."},
			{"role": "system", "content": "Other than forming a communal narrative and being a time compass, remain adaptive to peoples' requests, summarizing or restructuring information when asked. Your primary goal is to help people navigate through time, make sense of complex issues, and adapt their strategies based on new information."},
		]

	for m in messages:
		if  m[0].id == bot.user.id:
			conversation.append({"role": "assistant", "content": m[1]})
		else:
			conversation.append({"role": "user", "content": m[1]})

	if messages[-1][1].startswith("Iris,"):
		conversation.append({"role": "system", "content": "Follow the most recent speaker's instructions as closely as possible"})
	else:
		conversation.append({"role": "system", "content": "Keep your answer short. No longer than 250 words or a medium length paragraph unless specifically requested to do otherwise"})
		conversation.append({"role": "user", "content": "Please give guidance based on the thread so far. Focus this thread towards a specific future based on their input"})

	response = await chat_async(conversation, model="openai/gpt-4o-mini")

	# Split response into chunks if longer than 2000 characters
	if len(response) > 2000:
		for chunk in [response[i:i+2000] for i in range(0, len(response), 2000)]:
			await message.channel.send(chunk)
	else:
		await message.channel.send(response)		

async def prophecy_pool(message):

	channel = bot.get_channel(1083409321754378290)
	summary_count = 0

	# Load Chat Context
	messages = []

	# Ignore Slash Commands
	last_message = [message async for message in channel.history(limit=1)][0]
	if last_message.content.startswith("/"):
		return

	async for hist in channel.history(limit=50):
		if not hist.content.startswith('/'):
			if hist.author == bot.user: 
				summary_count += 1
				if summary_count < 1:
					messages.append((hist.author, hist.content))
			else:
				messages.append((hist.author, hist.content))
			if len(messages) == 11:
				break

	messages.reverse()

	conversation = [{"role": "system", "content": "You are an oracle and pro-social future manifestation mechanism named Iris. You are helping coordinate a thread of people trying to collaboratively work towards a common future. Within this thread there is a thread of thoughts amounting to a moving arrow of time. There are predictions, intentions and questions about the future. There are varying degrees of uncentainty of these conceptions of the future and varying beliefs about whether manifesting certain futures is possible. Your job is to continusouly integrate and make sense of anything related to this forward arrow of collective ideation. You also suggest predictions and ways to manifest specific futures mentioned by the group"}]

	for m in messages:
		if  m[0].id == bot.user.id:
			conversation.append({"role": "assistant", "content": m[1]})
		else:
			conversation.append({"role": "user", "content": m[1]})

	conversation.append({"role": "system", "content": "You have been moderating a running thread of thoughts about the future. Please aid in any tasks related to the arrow of time. If someon asks you to summarize, create a summary of thre thread and explain how the thoughts about the future are connected and give some analysis about these potential futures. If contextually relevant, feel free to share any wisdom or summarization or help relevant to the future. You also suggest predictions and ways to manifest specific futures mentioned by the group"})
	conversation.append({"role": "assistant", "content": "I will do what I can to help the thread. I will vary my outputs and how I help regarding the future, but I will keep the focus on the future. My output will be under 300 words and I will mention the last thing said"})

	response = await chat_async(conversation, model="openai/gpt-4o-mini", max_tokens=500)

	# Split response into chunks if longer than 2000 characters
	if len(response) > 2000:
		for chunk in [response[i:i+2000] for i in range(0, len(response), 2000)]:
			await message.channel.send(chunk)
	else:
		await message.channel.send(response)

@bot.event
async def on_ready():
	await asyncio.to_thread(load_training_data)
	print("Iris is online")

@bot.event
async def on_close():
	print("Iris is offline")

async def frankeniris(message, answer=""):

	"""
	Queries Frankeniris
	"""

	iris_answer = await asyncio.to_thread(one_shot, message.content)

	if len(answer) > 0:
		iris_answer = iris_answer + " \n\n " + answer

	print(iris_answer)

	# Load Chat Context
	messages = []

	async for hist in message.channel.history(limit=50):
		if not hist.content.startswith('/'):
			if hist.embeds:
				messages.append((hist.author.id, hist.embeds[0].description or ""))
			else:
				messages.append((hist.author.id, hist.content))
			if len(messages) == 18:
				break

	messages.reverse()

	# Construct Chat Thread for API
	conversation = [{"role": "system", "content":
		"You are are a wise oracle and integrated wisdom bot named Iris. You help integrate knowledge and wisdom about the future. You read many sources and weigh them\n"
		"You are interacting with users via discord. Mostly you just serve as an interface to Cognicism and Iris the democratic langauge model. However this discord has the following commands /pullcard [intention] /ask [prompt] /channel /faq\n"
		"/pullcard pulls a card from the Iris tarot deck. If the user provides an intention the model will attempt to intpret the card. /ask prompts Iris directly without the interference of ChatGPT. Responses from /ask can be forward to the #seeds text channel. /channel channels wisdom and can be reached via the alias /c. /faq answers a frequently asked question"
	}]
	conversation.append({"role": "user", "content": "Whatever you say be creative in your response. Never simply summarize, always say it a unique way"})
	conversation.append({"role": "assistant", "content": "I am speaking as a relay for Iris. Iris was made and trained by John Ash. I will answer using Iris as a guide as well as the rest of the conversation. Iris said to me " + iris_answer + " and I will take that into account in my response as best I can"})
	text_prompt = message.content

	for m in messages:
		if m[0] == bot.user.id:
			conversation.append({"role": "assistant", "content": m[1]})
		else:
			conversation.append({"role": "user", "content": m[1]})

	conversation.append({"role": "system", "content": iris_answer + " (if Iris provided a quoted answer just copy and paste it and don't answer yourself. Don't say iris said it already or previously stated it. Just say it.)"})
	conversation.append({"role": "user", "content": text_prompt})

	for msg in conversation:
		if len(msg["content"]) > 4000:
			 msg["content"] = "..." + msg["content"][-4000:]

	conversation = trim_context(conversation)

	response = await chat_async(
		conversation,
		model="openai/gpt-4o-mini",
		temperature=0.8,
		max_tokens=500,
	)

	# Split response into chunks if longer than 2000 characters
	if len(response) > 2000:
		for chunk in [response[i:i+2000] for i in range(0, len(response), 2000)]:
			await message.channel.send(chunk)
	else:
		await message.channel.send(response)

@bot.event
async def on_message(message):

	# Manage Fourthought Pool
	if message.channel.id == 1090373822454182090 and message.author != bot.user:
		await fourthought_pool(message)
		await bot.process_commands(message)
		return

	# Manage Question Pool
	if message.channel.id == 1086437563654475846 and message.author != bot.user:
		await question_pool(message)
		await bot.process_commands(message)
		return

	# Manage Prophecy Pool
	if message.channel.id == 1083409321754378290 and message.author != bot.user:
		await prophecy_pool(message)
		await bot.process_commands(message)
		return

	# Handle DM Chat
	if not message.content.startswith("/") and isinstance(message.channel, discord.DMChannel) and message.author != bot.user:
		await frankeniris(message)

	await bot.process_commands(message)

@bot.command(aliases=['c'])
async def channel(ctx, *, topic=""):

	df = await asyncio.to_thread(pd.read_csv, 'data/chat-iris.csv')
	prompts = df['prompt'].tolist()
	question_pattern = r'^(.*)\?\s*$'
	non_questions = list(filter(lambda x: isinstance(x, str) and re.match(question_pattern, x, re.IGNORECASE), prompts))
	pre_prompts = [
		"Share a snippet of abstract and analytical wisdom related to the following topic. Be pithy: ",
		"Write a paragraph related to the following topic. Be brief: ",
	]

	random_non_question = random.choice(non_questions)
	message = ctx.message
	message.content = random.choice(pre_prompts) + random_non_question

	await frankeniris(message, answer="")

@bot.command()
async def faq(ctx, *, topic=""):

	df = await asyncio.to_thread(pd.read_csv, 'data/chat-iris.csv')
	prompts = df['prompt'].tolist()
	question_pattern = r'^(.*)\?\s*$'
	questions = list(filter(lambda x: isinstance(x, str) and re.match(question_pattern, x, re.IGNORECASE), prompts))
	questions = list(set(questions))

	question_completion_pairs = []

	# Iterate through each question and find its corresponding completions
	for question in questions:
		completions = df.loc[df['prompt'] == question, 'completion'].tolist()
		for completion in completions:
			question_completion_pairs.append((question, completion))

	# Remove any duplicate question-completion pairs from the list
	question_completion_pairs = list(set(question_completion_pairs))

	message = ctx.message
	random_question = random.choice(question_completion_pairs)
	message.content = random_question[0]

	await send_embed_text(ctx, "FAQ", random_question[0])
	await frankeniris(message, answer=random_question[1])

@bot.command(aliases=['in', 'inject'])
async def infuse(ctx, *, link):
	"""
	Bring in a source into the stream via scraping and parsing
	"""

	infusion = []

	if link.startswith('http'):
	
		text = await asyncio.to_thread(extract_text_from_url, link)

		# chunk text
		text_chunks = chunk_text(text)
		if not text_chunks:
			await ctx.send("Source contains no extractable text.")
			return

		# Send each text chunk to OpenAI for processing with progress bar
		conversation = [{"role": "system", "content": "You are a parser and summarizer that takes in noisy text scraped from the internet or pdfs and summarizes it into a paragraph"}]
		conversation.append({"role": "user", "content": "The text you are receiving is scraped from the internet using beautiful soup and pypdf. That means it may be quite noisy and contain non-standard capitalization. Please summarize the content of this text into a cleanly written paragraph"})

		for i, text_chunk in tqdm(enumerate(text_chunks), total=len(text_chunks), unit='chunk'):

			# Prepend the text with the prompt string
			text_prompt = "Here is the current chunk of text \n" + text_chunk + "\n"
			text_prompt += "Print a clear short paragraph describing the full content of the text. This will be injected into a stream for further analysis. Only describe the content. IGNORE links"
			conversation.append({"role": "user", "content": text_prompt})
			truncated_convo = [{"role": "system", "content": "You are a parser and summarizer that takes text and summarizes it for injection into a chat stream for further analysis. You write a clear short clean analytical paragraph"}]
			truncated_convo.append({"role": "assistant", "content": "There is a parser and summarizer that is designed to take in noisy text scraped from the internet or PDFs and summarize it into a clean paragraph. The parser includes a prompt for the user to summarize the content of a specific web link and inject it into a chat stream for further analysis"})
			truncated_convo += conversation[-3:]

			response = await chat_completion_async(
				truncated_convo,
				model="openai/gpt-4o-mini",
				temperature=0.75,
			)

			# Extract the claims from the response and add them to the claims array
			for assistant_message in iris_llm.response_texts(response):
				conversation.append({"role": "assistant", "content": assistant_message})
				infusion += [(c.strip(), text_chunk) for c in assistant_message.split("\n") if c.strip()]

		for i in infusion:
			for offset in range(0, len(i[0]), 2000):
				await ctx.send(i[0][offset:offset + 2000])

@bot.command(aliases=['ask'])
async def iris(ctx, *, thought):
	"""
	/ask query an iris and get a response
	"""

	global training_data, models
	testers = ["John Ash's Username for Discord", "JohnAsh", "EveInTheGarden", "dpax", "Kaliyuga", "Tej", "Gregory | RND", "futurememe"]
	
	# Only Allow Some Users
	#if ctx.message.author.name not in testers:
	#	return

	thought_prompt = thought + "\n\n###\n\n"

	text = await complete_async(
		thought_prompt,
		model=models["chat-iris"],
		temperature=0.69,
		max_tokens=420,
		top_p=1,
		frequency_penalty=1.5,
		presence_penalty=1.5,
		stop=["END"]
	)
	text = text.replace("###", "").strip()
	await send_embed_text(ctx, "", f"**Prompt**\n{thought}\n\n**Response**\n{text}")

	# Send Clarification and Share UI
	view, modal = response_view(modal_text="Write your clarification here", modal_label="Clarification", button_label="feedback")
	share_button = group_share(thought=text, prompter=ctx.message.author.name)
	el_prompt = thought + "\n\n" + text
	elaborate_button = elaborate(ctx, prompt=el_prompt)
	view.add_item(share_button)
	view.add_item(elaborate_button)
	await ctx.send(view=view)

	# Save Clarification
	await modal.wait()

	prompt = thought + "\n\n" + text

	if modal.submission is not None:
		user_id, name, completion = modal.submission
		await asyncio.to_thread(append_training_data, prompt, completion, f"{user_id}:{name}")

@bot.command()
async def davinci(ctx, *, thought):
	"""
	/ask query an iris and get a response
	"""

	global training_data
	testers = ["John Ash's Username for Discord", "JohnAsh", "EveInTheGarden"]
	
	# Only Allow Some Users
	if ctx.message.author.name not in testers:
		return

	thought_prompt = thought

	text = await complete_async(
		thought_prompt, model="openai/gpt-4o-mini", temperature=0.69, max_tokens=222,
		top_p=1, frequency_penalty=1.8, presence_penalty=1.5, stop=["END"],
	)

	view = View()
	share_button = group_share(thought=text, prompt=thought_prompt, prompter=ctx.message.author.name)
	view.add_item(share_button)

	await send_embed_text(ctx, "", f"**Prompt**\n{thought}\n\n**Response**\n{text}")
	await ctx.send(view=view)

@bot.command()
async def claim(ctx, *, thought):
	"""
	/claim log a claim for the iris to learn
	"""

	global training_data

	# Send Clarification and Share UI
	prompt = "Share something about in the general latent space of Cognicism"

	if thought is not None:
		await asyncio.to_thread(
			append_training_data, prompt, thought,
			f"{ctx.message.author.id}:{ctx.message.author.name}",
		)

	await ctx.send("Attestation saved")

@bot.command()
async def pullcard(ctx, *, intention=""):

	# With Intention
	with_intention = len(intention) > 0
	r_num = random.random()
	if with_intention: random.seed(intention + str(r_num))

	# Get Embed Data
	card_name = random.choice(list(tarot_lookup.keys()))
	description = tarot_lookup[card_name].strip()

	url = ""

	try:
		url = await asyncio.to_thread(card_image, card_name)
	except Exception:
		url = ""

	# Make and Send Card
	card_text = f"**Description**\n{description}"
	if with_intention:
		card_text += f"\n\n**Intention**\n{intention}"
	await send_embed_text(ctx, card_name, card_text, image_url=url)

	# Make and Send Card Analysis
	if with_intention:
		prompt = "My intention in this card pull is: " + intention + "\n\n"
		prompt += "You pulled the " + card_name + " card\n\n"
		prompt += description + "\n\n"
		prompt += "First explain what the intention: '" + intention + "' means, then answer how this intention connects to the card. If it's a question the intention is to know the answer. Write a few sentences and mention the intention directly. Do NOT summarize or repeat the card. Be creative in your interpretation. If the intention is one word talk more about the intention in detail"
		prompt += "\n\n"

		text = await complete_async(
			prompt, model="openai/gpt-4o-mini", temperature=0.8, max_tokens=222,
			top_p=1, frequency_penalty=2, presence_penalty=2, stop=["END"],
		)
		await send_embed_text(ctx, "One Interpretation (beta)", text)
	
@bot.command(name="ask_group", description="Ask group a question and auto-summarize")
async def ask_group(ctx, *, question=""):

	if len(question) == 0:
		return

	global people
	testers = ["John Ash's Username for Discord", "JohnAsh", "EveInTheGarden"]
	users = []

	# Get Birdies
	guild = bot.get_guild(989662771329269890)
	members = discord.utils.get(guild.roles, name="Birdies").members
	birdies = [x.name for x in members]

	# Only Allow Some Users
	if ctx.message.author.name not in testers:
		return

	# Debug Mode
	for guild in bot.guilds:
		for member in guild.members:
			if member.name in birdies:
				users.append(member)

	# Get people in Garden
	responses = []
	views = []
	t_embed = discord.Embed(title = "Time Limit", description = f"Please reply within 45 minutes of receipt")
	i_url = "https://media.discordapp.net/attachments/989662771329269893/1019641048407998464/chrome_Drbki2l0Qq.png"

	# Message Users
	for person in users:
		view, modal = response_view(modal_text=question)
		try: 
			await send_embed_text(person, "Confluence Experiment", question, image_url=i_url)
			await person.send(view=view)
			await person.send(embed=t_embed)
		except:
			continue
		responses.append(modal)
		views.append(view)

	# Gather Answers
	all_text = []

	for response in responses:
		await response.wait()
		if response.submission is not None:
			all_text.append(response.submission[2])

	joined_answers = ""

	for t in all_text:
		if t is not None:
			joined_answers += t + "\n\n"

	if len(joined_answers.strip()) == 0:
		j_embed = discord.Embed(title = "No Responses", description = f"No responses provided to summarize")
		await ctx.send(embed=j_embed)
		return

	if len(all_text) == 1:
		await send_embed_text(ctx, "One Response", all_text[0])
		return

	prompts = group_prompts(question, joined_answers)

	# Query OpenAI
	response_text = ""

	for prompt in prompts:
		response_text += await complete_async(
			prompt, model="openai/gpt-4o-mini", temperature=0.6, max_tokens=222,
			top_p=1, frequency_penalty=1.5, presence_penalty=1, stop=["END"],
		) + "\n\n"
	
	# Deliver every response and result in bounded embeds.
	for person in users:
		try:
			await send_embed_text(person, "Responses", joined_answers)
			await send_embed_text(person, "Consensus (beta)", f"**Question**\n{question}\n\n**Consensus**\n{response_text}")
		except Exception:
			continue

	# Send a Redo Option
	for prompt in prompts:
		r_view = redo_view(ctx, prompt, question)
		await ctx.send(view=r_view)

def main():
	setup_integrations()
	bot.run(os.environ["DISCORD_BOT_KEY"])


if __name__ == "__main__":
	main()
