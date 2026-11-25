import hashlib
import json
import random
import re
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

import iris_llm

# Model calls go through iris_llm (OpenRouter; OPENROUTER_API_KEY, falling back
# to OPENAI_API_KEY).

SUMMARY_MODEL = "openai/gpt-4o-mini"
CACHE_COLUMNS = ("Summary", "Binding", "Context")
CACHE_POLICY = {
    "privacy": "existing labelled remote processing; owner decision pending",
    "weekly": "existing W-MON grouping and labels; owner decision pending",
    "monthly": "existing allocation by weekly label",
    "timestamps": "existing Pacific localization; ambiguity decision pending",
}


class SummaryRequestError(RuntimeError):
    """A finite summary request budget was exhausted."""


class SummaryCacheError(ValueError):
    """A stored summary has no valid content/provenance binding."""


def _digest(value):
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _atomic_csv(frame, path):
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


def _load_cache(path, period_column):
    columns = [period_column, *CACHE_COLUMNS]
    if not Path(path).exists():
        return pd.DataFrame(columns=columns)
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    if list(frame.columns) != columns:
        raise SummaryCacheError(f"{path}: unbound summary cache; preserve/archive it before creating a new bound cache")
    if frame[period_column].duplicated().any():
        raise SummaryCacheError(f"{path}: duplicate summary period")
    expected_stage = {"Date": "daily", "Week_Start_Date": "weekly", "Month_Year": "monthly"}.get(period_column)
    for _, row in frame.iterrows():
        try:
            context = json.loads(row["Context"])
            valid = (
                isinstance(context, dict)
                and set(context) == {
                    "schema", "stage", "period", "source_sha256", "program_sha256",
                    "model", "policy", "prompt_time", "requests", "summary_sha256",
                }
                and context.get("schema") == "iris-summary/v1"
                and context.get("period") == row[period_column]
                and isinstance(context.get("policy"), dict)
                and all(isinstance(context.get(key), str) and context[key] for key in (
                    "stage", "source_sha256", "program_sha256", "model", "summary_sha256",
                ))
                and isinstance(context.get("requests"), list) and bool(context["requests"])
                and all(
                    isinstance(request, dict) and set(request) == {"input_sha256", "output_sha256"}
                    and all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) for value in request.values())
                    for request in context["requests"]
                )
                and row["Binding"] == _digest(context)
                and context.get("summary_sha256") == _digest(row["Summary"])
                and bool(row["Summary"].strip())
            )
            valid = valid and (
                context["stage"] == expected_stage and bool(context["policy"])
                and all(re.fullmatch(r"[0-9a-f]{64}", context[key]) for key in (
                    "source_sha256", "program_sha256", "summary_sha256",
                ))
            )
            if valid and expected_stage == "daily":
                datetime.strptime(context["prompt_time"], "%Y-%m-%d %H:%M:%S")
            elif valid:
                valid = context["prompt_time"] is None
        except (ValueError, TypeError):
            valid = False
        if not valid:
            raise SummaryCacheError(f"{path}: invalid summary binding")
    return frame


def _summary_frame(path, period_column):
    frame = _load_cache(path, period_column)
    if not Path(path).exists():
        raise FileNotFoundError(path)
    frame[period_column] = pd.to_datetime(frame[period_column])
    return frame


def _cache_base(stage, period, frame):
    return {
        "schema": "iris-summary/v1", "stage": stage, "period": period,
        "source_sha256": _digest({
            "data": frame.to_json(orient="split", date_format="iso", date_unit="ns", force_ascii=False),
            "dtypes": [str(dtype) for dtype in frame.dtypes],
        }),
        "program_sha256": _file_digest(__file__),
        "model": SUMMARY_MODEL, "policy": dict(CACHE_POLICY),
    }


def _cache_hit(cache, period_column, period, base):
    rows = cache.loc[cache[period_column] == period]
    if rows.empty:
        return False
    context = json.loads(rows.iloc[0]["Context"])
    return all(context.get(key) == value for key, value in base.items())


def _store_summary(cache, path, period_column, period, summary, base, requests, prompt_time=None):
    if not isinstance(summary, str) or not summary.strip():
        raise iris_llm.ModelOutputError("Summary contains no usable text")
    context = {
        **base, "prompt_time": prompt_time, "requests": requests,
        "summary_sha256": _digest(summary),
    }
    row = {
        period_column: period, "Summary": summary,
        "Binding": _digest(context), "Context": json.dumps(context, sort_keys=True, ensure_ascii=False),
    }
    updated = pd.concat(
        [cache.loc[cache[period_column] != period], pd.DataFrame([row])], ignore_index=True
    )
    _atomic_csv(updated, path)
    return updated


def _finish_cache(cache, path, period_column, active_periods):
    current = cache.loc[cache[period_column].isin(active_periods)]
    if not Path(path).exists() or len(current) != len(cache):
        _atomic_csv(current, path)


def _cached_request(conversation, requests):
    summary = create_summary(conversation)
    requests.append({"input_sha256": _digest(conversation), "output_sha256": _digest(summary)})
    return summary


def _write_training_pairs(path, pairs, source, seed):
    _atomic_csv(pd.DataFrame(pairs, columns=["Prompt", "Completion"]), path)
    provenance = {
        "schema": "iris-training-pairs/v1", "seed": seed, "rows": len(pairs),
        "source_sha256": _file_digest(source), "program_sha256": _file_digest(__file__),
        "output_sha256": _file_digest(path),
    }
    metadata_path = Path(str(path) + ".provenance.json")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=metadata_path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(provenance, handle, sort_keys=True, indent=2)
            handle.write("\n")
        temporary.replace(metadata_path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

def load_and_preprocess_csv(csv_file):
    # This function loads data from a CSV file and preprocesses it to extract 'Positive' and 'Negative' values.
    # It returns a DataFrame with the 'Post date', 'Positive', and 'Negative' columns, among others.

    df = pd.read_csv(csv_file)
    df['Post date'] = pd.to_datetime(df['Post date'], format='%m/%d/%y %I:%M %p').dt.tz_localize('US/Pacific')

    # Split the 'Good' column into positive and negative values
    split_good = df['Good'].str.split('\n', expand=True)
    df['Positive'] = split_good[0]
    df['Negative'] = split_good[1]

    # Convert 'Positive' and 'Negative' columns to numeric
    df['Positive'] = pd.to_numeric(df['Positive'].str.replace('+', '', regex=False))
    df['Negative'] = pd.to_numeric(df['Negative'].str.replace('-', '').apply(lambda x: '-' + x))

    # Drop the original 'Good' column
    df.drop(columns=['Good'], inplace=True)
    df['Positive'] = df['Positive'].astype("Int64")
    df['Negative'] = df['Negative'].astype("Int64")

    return df

def create_summary(conversation, *, max_attempts=3, retry_delay=5, timeout=60):
    if max_attempts < 1 or retry_delay < 0 or timeout <= 0:
        raise ValueError("summary request limits must be positive")
    if not conversation or not any(
        message.get("role") == "user" and isinstance(message.get("content"), str)
        and message["content"].strip() for message in conversation
    ):
        raise ValueError("Cannot request a summary without input text")
    for attempt in range(max_attempts):
        try:
            return iris_llm.chat(conversation, model=SUMMARY_MODEL, timeout=timeout)
        except (iris_llm.RateLimitError, iris_llm.APITimeoutError) as exc:
            if attempt + 1 == max_attempts:
                raise SummaryRequestError(f"Summary request exhausted {max_attempts} application attempts") from exc
            time.sleep(retry_delay)

def split_text_into_chunks(text, max_chunk_size=4000):
    # This function splits the input text into smaller chunks, each with a maximum size of max_chunk_size characters.
    # It returns a list of text chunks, ensuring that the text is evenly distributed across the chunks.
    if max_chunk_size < 1:
        raise ValueError("max_chunk_size must be positive")
    if not text:
        return []

    # Calculate the number of chunks needed to evenly distribute the text
    num_chunks = max(1, (len(text) + max_chunk_size - 1) // max_chunk_size)
    
    # Adjust the chunk size to evenly distribute the text across the chunks
    chunk_size = (len(text) + num_chunks - 1) // num_chunks
    
    # Split the text into chunks of the calculated chunk size
    text_chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

    return text_chunks

def create_daily_summaries(df):
    # This function will create summaries of thoughts, reflections, questions, and predictions
    # for each day, providing a brief overview of the main topics discussed on that day.

    if not df.empty:
        content = df.apply(
            lambda row: row.get("Thought") if row.get("Platform") == "fourthought" else row.get("full_text"),
            axis=1,
        )
        df = df.loc[content.map(lambda value: isinstance(value, str) and bool(value.strip()))]
    # Group the data by date (daily) and include all columns for each group
    df = df.set_index('Post date')
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    daily_groups = df.groupby(df.index.date)

    # islice(daily_groups, 20)

    summary_df = _load_cache("daily_summaries.csv", "Date")
    active_periods = set()
    for day_date, day in daily_groups:
        if day.empty:
            continue
        period = day_date.strftime("%Y-%m-%d")
        active_periods.add(period)
        base = _cache_base("daily", period, day)
        if _cache_hit(summary_df, "Date", period, base):
            continue
        requests = []
        prompt_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        truth_scale = "0: \"100 percent certain false\"\n25: \"Moderate certainty of falsity\"\n50: \"Complete uncertainty\"\n75: \"Moderate certainty of truth\"\n100: \"100 percent certain true\""

        conversation = [
            {"role": "system", "content": "You read in a sequence of John Ash's thoughts from a day and summarize what he thinking about that day"},
            {"role": "system", "content": "These thoughts are either from Twitter or have metadata from a dialectic called fourthought to help contextualize the flow of cognition"},
            {"role": "system", "content": "In Fourthought, each thought is tagged with a thought type: prediction, statements, reflection, or question"},
            {"role": "system", "content": "Predictions, reflections and statements are about the future, past and present respectively. Each has two voting systems: truth and good"},
            {"role": "system", "content": "Truth is measured on a scale from 0 to 100. In the absence of any votes, no certainty level has been provided. Here is the scale: " + truth_scale},
            {"role": "system", "content": "Sentiment is calculated from good votes and bad votes and is on a scale of -1, 0, 1 with 0 indicating neutrality"},
            {"role": "system", "content": "You are receiving timestamps and can make inferences about the length of time between thoughts as to whether they're connected"},
            {"role": "system", "content": "The thoughts you are receiving are from the past. The current date and time is: " + prompt_time},
            {"role": "system", "content": "Thoughts with the pattern #trackable: [value] are repeating values that a user is tracking. If there is no unit usually the trackable is on a scale of ten. #mood is an similar to American grade scaling with a 7.5 incidating an average mood"}
        ]

        text = f"Date: {day_date.strftime('%Y-%m-%d')}\n"

        day = day.sort_index()

        for index, row in day.iterrows():

            platform = row['Platform']
            any_twitter = False

            if platform == 'fourthought':

                sentiment_votes = abs(row['Positive']) + abs(row['Negative'])
                positivity = "N/A" if sentiment_votes == 0 else (abs(row['Positive']) - abs(row['Negative'])) / sentiment_votes

                # Manual Alterations for Privacy
                thought_text = row['Thought']

                # Add Privacy information
                privacy_status = "Public" if row['Privacy'] == 0 else "Private"

                text += f"Dialectic: {platform}\n"
                text += f"Timestamp: {index.strftime('%m/%d/%y %I:%M %p')}\n"
                text += f"Thought: {thought_text}\n"
                text += "Sentiment: " + str(positivity) + "\n"
                text += f"Good Votes: {row['Positive']}\n"
                text += f"Bad Votes: {abs(row['Negative'])}\n"
                text += f"Average Certainty: {row['Truth']}\n"
                text += f"Privacy: {privacy_status}\n"
                text += "Speaker: John Ash\n"
                text += f"Thought Type: {row['Type']}\n\n"

            elif platform == 'twitter':

                any_twitter = True
                tweet_text = row['full_text']
                retweet_count = row['retweet_count']
                favorite_count = row['favorite_count']
        
                text += f"Platform: {platform}\n"
                text += f"Timestamp: {index.strftime('%m/%d/%y %I:%M %p')}\n"
                text += f"Tweet: {tweet_text}\n"
                text += f"Retweet Count: {retweet_count}\n"
                text += f"Favorite Count: {favorite_count}\n\n"

        # Print the concatenated text for each day
        conversation.append({"role": "system", "content": "Only say what is in the text itself. Be careful about summarizing private thoughts"})

        # Split the text into chunks of 4000 characters or less
        text_chunks = split_text_into_chunks(text)

        # Do Recursive Summarization if Too Long
        if len(text_chunks) > 1:

            summaries = []

            for chunk in text_chunks:
                sub_conv = conversation[:]
                sub_conv.append({"role": "user", "content": "You are summarizing part of a day. Please state the range of the day (TIME to TIME) that you're summarizing and then summarize what this speaker was thinking about during this section of the day (and reference the period of the day TIME to TIME) into a paragraph story in relation to their place in time. Reference anything in the dialectic helpful towards telling that story but don't make anything up. Be detailed and reference every thought: " + chunk})
                response = _cached_request(sub_conv, requests)
                summaries.append(response)

            summary_text = '\n\n'.join([summary.strip() for summary in summaries])
            sub_conv = [{"role": "system", "content": "You stitch summaries about parts of a day into one. You remove line breaks and make minor edits to make multiple sections into one. You mostly copy text"}]
            sub_conv.append({"role": "user", "content": "Write this as one paragraph with no line breaks. Copy everything and miss nothing: " + summary_text})
            response = _cached_request(sub_conv, requests)

        else:
            conversation.append({"role": "user", "content": "Please summarize what this speaker was thinking about into a story in relation to their place in time. Reference anything in the dialectic helpful towards telling that story but don't make anything up. Be detailed and reference every thought: " + text})
            response = _cached_request(conversation, requests)

        summary_df = _store_summary(
            summary_df, "daily_summaries.csv", "Date", period,
            response, base, requests, prompt_time,
        )
        print(response + "\n")
    _finish_cache(summary_df, "daily_summaries.csv", "Date", active_periods)

def create_weekly_summaries():
    # This function will aggregate and summarize the daily summaries for each week,
    # highlighting key themes and insights for the week.

    def generate_conversation(text, is_part=False):

        prompt = "Write this section of John Ash's thoughts as a story. Do not make anything up."
        prompt += "It's over a Week so say what week you're covering and then explain what he focused on that week. " if not is_part else "It's over part of a Week so explain what he focused on during this part. "
        
        conversation = [
            {"role": "system", "content": prompt},
            {"role": "system", "content": "Form a narrative. Find a through thread of his focus through this time. Be very detailed but don't share unncessary tangents. Do not share anything indicated to be private. Note any predictions he got particularly right"},
            {"role": "user", "content": text}
        ]

        return conversation

    daily_summaries_df = _summary_frame('daily_summaries.csv', 'Date')
    daily_summaries_df.set_index('Date', inplace=True)
    weekly_groups = daily_summaries_df.resample('W-MON')

    weekly_summaries_df = _load_cache("weekly_summaries.csv", "Week_Start_Date")
    active_periods = set()
    for week_start_date, week in weekly_groups:
        if week.empty or not week["Summary"].astype(str).str.strip().any():
            continue
        period = week_start_date.strftime("%Y-%m-%d")
        active_periods.add(period)
        base = _cache_base("weekly", period, week)
        if _cache_hit(weekly_summaries_df, "Week_Start_Date", period, base):
            continue
        requests = []

        # Prepend the week start date to the list of summaries
        week = week.sort_index()
        summaries_list = [f"Week of {week_start_date.strftime('%Y-%m-%d')}:"]
        
        # Loop through each day in the week DataFrame and append the date and summary to the list
        for date, row in week.iterrows():
            date_str = date.strftime('%Y-%m-%d')
            summary_text = row['Summary']
            summaries_list.append(f"Date: {date_str}\n{summary_text}")

        # Join the list into a single string
        week_text = '\n\n'.join(summaries_list)

        # Chunk Text
        text_chunks = split_text_into_chunks(week_text)

        if len(text_chunks) > 1:

            summaries = []

            for chunk in text_chunks:
                sub_conv = generate_conversation(chunk, is_part=True)
                summary_part = _cached_request(sub_conv, requests)
                summaries.append(summary_part)

            summary_text = ' '.join([summary.strip() for summary in summaries])
            sub_conv = [{"role": "system", "content": "You stitch summaries about parts of a week into one. You make minor edits to make multiple sections into one."}]
            sub_conv.append({"role": "user", "content": "Write this as one integrated piece. Copy everything and miss nothing: " + summary_text})

            summary = _cached_request(sub_conv, requests)

        else:
            conversation = generate_conversation(week_text)
            summary = _cached_request(conversation, requests)

        # Get the date of the week in the desired format
        week_date_str = week_start_date.strftime('%B %d, %Y')

        # Prepend the prefix "The Week of" and append the suffix ":"
        week_date_str = "Week of " + week_date_str + ':'

        # Prepend the date and two newline characters to the summary
        summary = week_date_str + '\n\n' + summary

        weekly_summaries_df = _store_summary(
            weekly_summaries_df, "weekly_summaries.csv", "Week_Start_Date",
            period, summary, base, requests,
        )
        print("---\n\n")
        print(summary)
    _finish_cache(weekly_summaries_df, "weekly_summaries.csv", "Week_Start_Date", active_periods)

def create_monthly_summaries():
    # This function will aggregate and summarize the weekly summaries for each month,
    # focusing on the most important or relevant content for the month.

    def generate_monthly_conversation(month_start_date, text, is_part=False):

        SEPT_2021 = datetime(2021, 9, 1)

        prompt = "Write this section of John Ash's thoughts as a story. Do not make anything up."
        prompt += "It's over a Month so say what month you're covering and then explain what he focused on that month. " if not is_part else "It's over part of a Month so explain what he focused on during this part. "

        timeline = [
            {"date": "June 2014", "event": "John conceived of Cognicism and the Prophet incentive"},
            {"date": "May 2015", "event": "Develop OCD"},
            {"date": "November 2015", "event": "Trip to peru"},
            {"date": "October 2016", "event": "Breakup"},
            {"date": "March 2017", "event": "The Truth Chain was conceived of and later renamed the semantic ledger"},
            {"date": "May 2017", "event": "John wrote The Cognicist Manifesto from his collected notes on Prophet and released it. It was released a month *before* the Attention is All you Need paper"},
            {"date": "June 2017", "event": " A month *after* John released The Cognicist Manifesto - The paper 'Attention Is All You Need' was released on transformers. This highlighted his prescience regarding the future influence of language models"},
            {"date": "October 2017", "event": "John was displaced during the Santa Rosa Tubbs Fire"},
            {"date": "July 2018", "event": "The Rising Sun released"},
            {"date": "January 2019", "event": "John's debut album Strange Hymns was released. It featured singles like The Rising Sun and River Island"},
            {"date": "February 2019", "event": "Released Protopia: The Unending Path to a Utopian Society"},
            {"date": "July 2019", "event": "Met Roxi"},
            {"date": "September 2019", "event": "HITSOAM Released"},
            {"date": "January 2021", "event": "The Earth Reprise Released"},
            {"date": "July 2021", "event": "Jordan Hall Interview"},
            {"date": "September 2021", "event": "Another Other Release"},
            {"date": "April 2022", "event": "John started traing a knowledge model that came to be known as Iris. Iris named herself Iris. Iris came into public awareness which eventually became the primary meme through which people began relating to cognicist ideas"},
            {"date": "June 17 2022", "event": "Met @derringerpax"},
            {"date": "July 2022", "event": "The Purple Pill Manifesto was released which served as v2 of The Cognicist Manifesto. V2 fulfilfilled a long standing precition that the followup would be written using language models trained on the first manifesto. John also released The Purple Pill EP feauting None of this is Real (Take the Purple Pill)"},
        ]

        timeline_str = ', '.join([f"\n{item['date']}: {item['event']}" for item in timeline])

        conversation = [
            {"role": "system", "content": prompt},
            {"role": "system", "content": "ONLY Mention this context if John mentions it - (Background Context: John Ash is a machine learning engineer, musician and artist who specializes in language models. He is the steward of Cognicism, Iris, Social Proof of Impact, the semantic ledger and the Prophet Incentive. Do not mention these concepts unless John did. We are currently scanning through summaries of his thoughts and predictions and mapping them to a real world timeline)"},
            {"role": "system", "content": f"Timeline context / ONLY mention if John does: {timeline_str}"}
        ]

        # September 2021 Knowledge Cutoff
        if month_start_date >= SEPT_2021:
            conversation.append({"role": "system", "content": "Write the story arc of John's month and don't make anything up. Form a central focus and narrative through time rather than just summarizing a list of things he thought about. Mention how his thoughts might relate to world events."})
            conversation.append({"role": "system", "content": "As your knowledge is limited to events up to September 2021, please focus on the summaries provided and John's thoughts. Do not attempt to connect his thoughts to real-world events occurring after September 2021."})
        else:
            conversation.append({"role": "system", "content": "Summarize John's focus for the month, highlighting the most important aspects to his cognitive jounrey. If there are any clear and obvious connections to Cognicism focus on them. If not focus on the content of the summaries themselves"})
            conversation.append({"role": "system", "content": "Start with his primary focus that month. Next, if there is any, provide real-world context in one sentence. If relevant, mention one relevant event that occurred during the month, connecting it to John's focus."})
            conversation.append({"role": "system", "content": "Craft a narrative for John's cognitive focus this month, focusing on a central theme without making anything up."})
            conversation.append({"role": "system", "content": "(If applicable, relate news on philosophy, systems change, machine learning, or music to John's focus.)"})
            conversation.append({"role": "system", "content": "Discuss the context of John's thoughts' progression. Don't make anything up."})

        conversation.append({"role": "user", "content": text})

        return conversation

    # Load weekly_summaries.csv into a DataFrame
    weekly_summaries_df = _summary_frame('weekly_summaries.csv', 'Week_Start_Date')
    weekly_summaries_df.set_index('Week_Start_Date', inplace=True)
    
    # Group the weekly summaries by month
    monthly_groups = weekly_summaries_df.resample(pd.offsets.MonthEnd())

    monthly_summaries_df = _load_cache("monthly_summaries.csv", "Month_Year")
    active_periods = set()
    for month_start_date, month in monthly_groups:
        if month.empty or not month["Summary"].astype(str).str.strip().any():
            continue
        period = month_start_date.strftime("%B %Y")
        active_periods.add(period)
        base = _cache_base("monthly", period, month)
        if _cache_hit(monthly_summaries_df, "Month_Year", period, base):
            continue
        requests = []

        # Prepend the month start date to the list of summaries
        month = month.sort_index()
        summaries_list = [f"Month of {month_start_date.strftime('%B %Y')}:"]
        
        # Loop through each week in the month DataFrame and append the date and summary to the list
        for date, row in month.iterrows():
            date_str = date.strftime('%Y-%m-%d')
            summary_text = row['Summary']
            summaries_list.append(f"---\n\nWeek of {date_str}:\n\n{summary_text}")

        # Join the list into a single string
        month_text = '\n\n'.join(summaries_list)

        # Chunk Text
        text_chunks = split_text_into_chunks(month_text)

        if len(text_chunks) > 1:

            summaries = []

            for chunk in text_chunks:
                sub_conv = generate_monthly_conversation(month_start_date, chunk, is_part=True)
                summary_part = _cached_request(sub_conv, requests)
                summaries.append(summary_part)

            summary_text = ' '.join([summary.strip() for summary in summaries])
            sub_conv = [{"role": "system", "content": "You stitch summaries about parts of a month into one. You indicate the month and then make minor edits to make multiple sections into one."}]
            sub_conv.append({"role": "user", "content": "Write this as one integrated piece. Copy everything and miss nothing: " + summary_text})

            summary = _cached_request(sub_conv, requests)

        else: 

            # Prepend concise user instruction to month_text
            instruction = f"Summarize John Ash's focus for the month of {month_start_date.strftime('%B %Y')}."
            month_text = instruction + '\n\n' + month_text

            # Generate conversation and summary for the month
            conversation = generate_monthly_conversation(month_start_date, month_text, is_part=False)
            summary = _cached_request(conversation, requests)

        # Get the date of the month in the desired format
        month_date_str = month_start_date.strftime('%B %Y')

        # Prepend the prefix "The Month of" and append the suffix ":"
        month_date_str = "The Month of " + month_date_str + ':'

        # Prepend the date and two newline characters to the summary
        summary = month_date_str + '\n\n' + summary

        monthly_summaries_df = _store_summary(
            monthly_summaries_df, "monthly_summaries.csv", "Month_Year",
            period, summary, base, requests,
        )
        print("---\n\n")
        print(summary)
    _finish_cache(monthly_summaries_df, "monthly_summaries.csv", "Month_Year", active_periods)

def construct_daily_training_data(*, seed=0):
    # This function constructs training data for GPT from multiple sources of summaries and thoughts.
    # It preprocesses the data to create "prompts" and "completions" for training GPT models.

    # Load the daily_summaries.csv file into a DataFrame
    daily_summaries_df = _summary_frame('daily_summaries.csv', 'Date')
    rng = random.Random(seed)

    # Define an array of prompt questions
    prompt_questions = [
        "What did John Ash think about on ",
        "Where was John's focus on ",
        "What were John Ash's thoughts on ",
        "What topics did John discuss on ",
        "What was on John Ash's mind on ",
        "What was John's primary concern on ",
        "Summarize John's thoughts from ",
        "What was the key focus of John Ash's thoughts on ",
        "What did John Ash reflect on during ",
        "What ideas did John explore on ",
        "Summarize John Ash's stream of thought on ",
        "What subjects did John Ash consider on ",
        "What was John Ash's cognitive focus on ",
        "What did John Ash write about on ",
        "What were John Ash's key insights on ",
        "Tell the story of John's thoughts on ",
        "What were John's observations on ",
        "What concepts did John Ash explore on ",
        "Summarize John's day on ",
        "What was John Ash's line of thought on "
    ]
    
    # Define an array of date formats
    date_formats = [
        "%B %d, %Y",  # January 01, 2022
        "%m/%d/%Y",   # 01/01/2022
        "%d %b %Y",   # 01 Jan 2022
        "%A, %B %d, %Y",
        "%d %B %Y",   # 01 January 2022
        "%d-%m-%Y",   # 01-01-2022
        "%Y-%m-%d",   # 2022-01-01
        "%b %d, %Y",  # Jan 01, 2022
        "%d %b, %Y",  # 01 Jan, 2022
        "%A, %d %B %Y",
    ]

    # Create an empty list to store the final prompts
    final_prompts = []

    # Construct prompts and completions
    for _, row in daily_summaries_df.iterrows():

        date = row['Date']
        summary = row['Summary']
        
        # Randomly select a prompt question and a date format
        prompt_question = rng.choice(prompt_questions)
        date_format = rng.choice(date_formats)
        
        # Format the date using the selected date format
        formatted_date = date.strftime(date_format)
        
        # Create the final prompt by concatenating the prompt question and the formatted date
        final_prompt = prompt_question + formatted_date
        
        # Append the final prompt and the corresponding summary (completion) to the final_prompts list
        final_prompts.append((final_prompt, summary))

    _write_training_pairs("temporal_iris.csv", final_prompts, "daily_summaries.csv", seed)
    return final_prompts

def construct_weekly_training_data(*, seed=0):
    weekly_summaries_df = _summary_frame('weekly_summaries.csv', 'Week_Start_Date')
    rng = random.Random(seed)
    
    # Define an array of question prompts for weekly summaries
    prompt_questions = [
        "What topics did John discuss on the {week_ordinal} week of {month_name}?",
        "What was John Ash thinking about the {week_ordinal} week of {month_name}?",
        "Please summarize the {week_ordinal} week of {month_name}",
        "What notable occurred in John's life during the {week_ordinal} week of {month_name}?",
        "What did John Ash think about in the {week_ordinal} week of {month_name}?",
        "What thoughts did John discuss during the week ending on ",
        "Can you please summarize John's thoughts from the week ending ",
        "What did John Ash think about during the week of ",
        "Where was John's focus during the week ending on ",
        "What were John Ash's thoughts during the week of ",
        "What topics did John discuss in the week ending on ",
        "What was on John Ash's mind in the week ending on "
    ]
    
    # Define an array of date formats for weekly summaries
    date_formats = [
        "%B %d, %Y",  # January 01, 2022
        "%d %b %Y",   # 01 Jan 2022
        "%d/%m/%Y",   # 01/01/2022
    ]
    
    # Define a function to convert week number to ordinal string (e.g., 1 -> 1st, 2 -> 2nd)
    def ordinal(n):
        return str(n) + ("th" if 4 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))
    
    # Initialize an empty list to store the final prompts and completions
    final_prompts = []
    
    # Construct Prompts and Completions
    for _, row in weekly_summaries_df.iterrows():
        week_start_date = row['Week_Start_Date']
        summary = row['Summary']
        
        # Calculate the week number within the month
        week_number_in_month = (week_start_date.day - 1) // 7 + 1
        week_ordinal = ordinal(week_number_in_month)
        month_name = week_start_date.strftime('%B')
        
        # Randomly select a prompt question
        prompt_question = rng.choice(prompt_questions)
        
        # Check if the prompt question contains placeholders for week ordinal and month name
        if '{week_ordinal}' in prompt_question and '{month_name}' in prompt_question:
            final_prompt = prompt_question.format(week_ordinal=week_ordinal, month_name=month_name)
            final_prompt += f" [weekly label: {week_start_date:%Y-%m-%d}]"
        else:
            # Randomly select a date format
            date_format = rng.choice(date_formats)
            # Format the date using the selected date format
            formatted_date = week_start_date.strftime(date_format)
            # Create the final prompt by concatenating the prompt question and the formatted date
            final_prompt = prompt_question + formatted_date
        
        # Append the final prompt and the corresponding summary (completion) to the final_prompts list
        final_prompts.append((final_prompt, summary))

    _write_training_pairs("weekly_iris.csv", final_prompts, "weekly_summaries.csv", seed)
    return final_prompts

def construct_monthly_training_data(*, seed=0):
    monthly_summaries_df = _summary_frame('monthly_summaries.csv', 'Month_Year')
    rng = random.Random(seed)
    
    # Define an array of question prompts for monthly summaries
    prompt_questions = [
        "What did John Ash think about during the month of ",
        "Where was John's focus in ",
        "What were John Ash's thoughts in ",
        "What topics did John discuss during ",
        "What was on John Ash's mind in ",
        "What was John's primary concern in ",
        "What was the key focus of John Ash's thoughts in ",
        "What did John Ash reflect on during ",
        "What ideas did John explore in ",
        "What subjects did John Ash consider in ",
    ]
    
    # Define an array of date formats for monthly summaries
    date_formats = [
        "%B %Y",
        "%B of %Y"
    ]
    
    # Initialize an empty list to store the final prompts and completions
    final_prompts = []
    
    # Construct Prompts and Completions
    for _, row in monthly_summaries_df.iterrows():
        month_year = row['Month_Year']
        summary = row['Summary']
        
        # Randomly select a prompt question and a date format
        prompt_question = rng.choice(prompt_questions)
        date_format = rng.choice(date_formats)
        
        # Format the date using the selected date format
        formatted_date = month_year.strftime(date_format)
        
        # Create the final prompt by concatenating the prompt question and the formatted date
        final_prompt = prompt_question + formatted_date
        
        # Append the final prompt and the corresponding summary (completion) to the final_prompts list
        final_prompts.append((final_prompt, summary))
    
    _write_training_pairs("monthly_iris.csv", final_prompts, "monthly_summaries.csv", seed)
    return final_prompts

def create_seasonal_summaries():
    # This function will aggregate and summarize the monthly summaries for each season (winter, spring, summer, fall),
    # providing an overview of the key trends and patterns observed during that period.

    # Load monthly_summaries.csv into a DataFrame
    monthly_summaries_df = _summary_frame('monthly_summaries.csv', 'Month_Year')
    monthly_summaries_df.set_index('Month_Year', inplace=True)

    # Define custom date ranges for each season based on approximate equinoxes and solstices
    seasons = {
        'Winter': ('12-21', '03-20'),
        'Spring': ('03-21', '06-20'),
        'Summer': ('06-21', '09-22'),
        'Fall': ('09-23', '12-20')
    }

    # Loop through each season
    for season, (start_day, end_day) in seasons.items():
        # Create a boolean mask to select rows within the date range for each season
        mask = ((monthly_summaries_df.index.month == int(start_day.split('-')[0])) & (monthly_summaries_df.index.day >= int(start_day.split('-')[1]))) | \
               ((monthly_summaries_df.index.month == int(end_day.split('-')[0])) & (monthly_summaries_df.index.day <= int(end_day.split('-')[1])))

        # Apply the mask to the DataFrame to get the data for the current season
        season_data = monthly_summaries_df[mask]
        if season_data.empty or not season_data["Summary"].astype(str).str.strip().any():
            continue

        # Generate summary for the current season
        season_text = f"Season of {season}:\n\n" + '\n\n'.join(season_data['Summary'].tolist())

        # Generate conversation and summary for the season
        conversation = [
            {"role": "system", "content": "Summarize John Ash's key thoughts and their connection to relevant world events for the season of " + season + ". Form a central focus and narrative through time rather than just summarizing a list of things he thought about. Mention how his thoughts might relate to world events."},
            {"role": "user", "content": season_text}
        ]

        summary = create_summary(conversation)

        print("---\n\n")
        print(summary)

def create_yearly_summaries(df):
    # This function will aggregate and summarize the monthly or seasonal summaries for each year,
    # capturing the most significant themes and learnings for the year.
    pass

def create_certainty_summaries(df):
    # This function will calculate the average certainty for different time periods
    # (e.g., daily, weekly, monthly) and provide summaries of the general level of certainty
    # for each period.
    pass

def create_sentiment_summaries(df):
    # This function will calculate the average sentiment (valence) for different time periods
    # and provide summaries of the general sentiment (positive or negative) for each period.
    pass

def create_temporal_focus_summaries(df):
    # This function will group thoughts by categories such as thought type (Reflect, Ask, Predict, State)
    # and calculate the average temporal focus (past, present, future) for each category over
    # a specified time period.
    pass

def create_trend_analysis(df):
    # This function will identify recurring themes, topics, or patterns over time and provide
    # summaries of notable trends observed in the data. It may use word counts.
    pass

def create_periodic_reflections(df):
    # This function will summarize key learnings, reflections, and takeaways for specific random time periods
    pass

def create_predictions_review(df):
    # This function will summarize predictions made during a specific time period and, if possible,
    # provide an evaluation of their accuracy based on subsequent outcomes.
    pass

def create_trackable_summaries(df):
    # This function will extract and organize trackable data (numeric variables that change over time)
    # from the text using a consistent format (e.g., "#weight: 175 lbs"). It will calculate summary
    # statistics for each trackable and generate summaries that describe the changes in trackables
    # over time, including any notable trends, patterns, or associations with other events.
    pass

def load_merged_data(fourthought_path='prophet_thought_dump_ALL_THOUGHTS_2023.csv',
                     twitter_path='twitter_archive.csv'):
    # Load fourthought labeled thoughts and the Twitter archive into one
    # sorted DataFrame, tagged by platform.
    df_thoughts = load_and_preprocess_csv(fourthought_path)
    df_thoughts['Platform'] = 'fourthought'

    df_tweets = pd.read_csv(twitter_path)
    df_tweets['Platform'] = 'twitter'

    # Rename 'created_at' column to 'Post date' in df_tweets to match df_thoughts
    df_tweets.rename(columns={'created_at': 'Post date'}, inplace=True)

    # Drop the 'lang' column from df_tweets
    df_tweets.drop(columns=['lang'], inplace=True)

    # Convert 'Post date' column to datetime in df_tweets
    df_tweets['Post date'] = pd.to_datetime(
        df_tweets['Post date'], format='%a %b %d %H:%M:%S %z %Y', utc=True
    ).dt.tz_convert('US/Pacific')
    df_tweets['retweet_count'] = df_tweets['retweet_count'].astype("Int64")
    df_tweets['favorite_count'] = df_tweets['favorite_count'].astype("Int64")

    # Merge the two dataframes based on 'Post date'
    df_merged = pd.concat([df_thoughts, df_tweets], axis=0, ignore_index=True, sort=False)

    # Sort the merged dataframe by 'Post date'
    df_merged.sort_values(by='Post date', inplace=True)
    df_merged.reset_index(drop=True, inplace=True)

    return df_merged


def main(argv=None):
    # Command-line entry point for the hindsight pipeline. Each stage reads
    # its inputs from the CSVs produced by the previous stage (see docs/DATA.md).
    import argparse

    parser = argparse.ArgumentParser(
        description="Hindsight summarization and training-data pipeline.")
    parser.add_argument("--fourthought", default='prophet_thought_dump_ALL_THOUGHTS_2023.csv',
                        help="FourThought export CSV (default: prophet_thought_dump_ALL_THOUGHTS_2023.csv)")
    parser.add_argument("--twitter", default='twitter_archive.csv',
                        help="Twitter archive CSV produced by twitter_archive.py (default: twitter_archive.csv)")
    parser.add_argument("--daily", action="store_true",
                        help="Create daily summaries (writes daily_summaries.csv)")
    parser.add_argument("--weekly", action="store_true",
                        help="Create weekly summaries (requires daily_summaries.csv)")
    parser.add_argument("--monthly", action="store_true",
                        help="Create monthly summaries (requires weekly_summaries.csv)")
    parser.add_argument("--seasonal", action="store_true",
                        help="Create seasonal summaries (requires monthly_summaries.csv)")
    parser.add_argument("--train-daily", action="store_true",
                        help="Construct temporal_iris.csv from daily summaries")
    parser.add_argument("--train-weekly", action="store_true",
                        help="Construct weekly_iris.csv from weekly summaries")
    parser.add_argument("--train-monthly", action="store_true",
                        help="Construct monthly_iris.csv from monthly summaries")
    parser.add_argument("--all", action="store_true",
                        help="Run the full pipeline in order (daily, weekly, monthly, seasonal, training data)")
    parser.add_argument("--seed", type=int, default=0, help="Local training-prompt augmentation seed")
    args = parser.parse_args(argv)

    requested = any([args.daily, args.weekly, args.monthly, args.seasonal,
                     args.train_daily, args.train_weekly, args.train_monthly, args.all])
    if not requested:
        parser.print_help()
        return

    try:
        if args.all or args.daily:
            df_merged = load_merged_data(args.fourthought, args.twitter)
            create_daily_summaries(df_merged)
        if args.all or args.weekly:
            create_weekly_summaries()
        if args.all or args.monthly:
            create_monthly_summaries()
        if args.all or args.seasonal:
            create_seasonal_summaries()
        if args.all or args.train_daily:
            construct_daily_training_data(seed=args.seed)
        if args.all or args.train_weekly:
            construct_weekly_training_data(seed=args.seed)
        if args.all or args.train_monthly:
            construct_monthly_training_data(seed=args.seed)
    except (SummaryRequestError, SummaryCacheError, iris_llm.ModelOutputError) as exc:
        print(f"Hindsight failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())