from openpipe import OpenAI
from typing import List
import ray
import json
import string

client = OpenAI()


restate_need_tools = [
    {
        "type": "function",
        "function": {
            "name": "restate_need",
            "description": "Restate the need in a single sentence from your perspective.",
            "parameters": {
                "type": "object",
                "properties": {
                    "restated_need": {
                        "type": "string",
                        "description": "The restated need.",
                    },
                },
                "required": ["restated_need"],
            },
        },
    }
]


def restate_need(need):
    completion = client.chat.completions.create(
        model="gpt-4-0613",
        messages=[
            {"role": "system", "content": "You are a helpful AI assistant."},
            {
                "role": "user",
                "content": f"""
Pretend you have the following need. State that need concisely in a single sentence from your perspective. The first word should be "I".

Need: {need}
""",
            },
        ],
        tools=restate_need_tools,
        tool_choice={
            "type": "function",
            "function": {
                "name": "restate_need",
            },
        },
    )

    return json.loads(completion.choices[0].message.tool_calls[0].function.arguments)[
        "restated_need"
    ]


generate_user_groups_tools = [
    {
        "type": "function",
        "function": {
            "name": "generate_user_groups",
            "description": "Generate a list of user groups who have a problem and a short reason why they have it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "all_user_groups": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "reason": {
                                    "type": "string",
                                    "description": "A short reason why the user group has the problem.",
                                },
                                "user_group": {
                                    "type": "string",
                                    "description": "The name of the user group.",
                                },
                            },
                            "required": ["reason", "user_group"],
                        },
                        "description": "The full of user groups who have the problem and a short reason why they have it.",
                    },
                    "top_3_user_groups": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "The top 3 user groups who have the problem the most.",
                    },
                },
                "required": ["user_groups"],
            },
        },
    }
]


def generate_user_groups(need) -> List[str]:
    completion = client.chat.completions.create(
        model="gpt-4-0613",
        messages=[
            {"role": "system", "content": "You are a helpful AI assistant."},
            {
                "role": "user",
                "content": """
List 7 user groups who have the following problem and a short reason why they have it. Then, list the top 3 groups who have the problem the most.""",
            },
            {
                "role": "user",
                "content": f"Problem: {need}",
            },
        ],
        tools=generate_user_groups_tools,
        tool_choice={
            "type": "function",
            "function": {
                "name": "generate_user_groups",
            },
        },
    )

    user_groups = json.loads(
        completion.choices[0].message.tool_calls[0].function.arguments
    )["top_3_user_groups"]

    return user_groups


summarize_tools = [
    {
        "type": "function",
        "function": {
            "name": "summarize",
            "description": "Summarize the reddit post and how it relates to the given need.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "The summary of the reddit post and how it relates to the need.",
                    },
                },
                "required": ["summary"],
            },
        },
    }
]


def generate_summarize_message(title, content, need):
    return f"""
Here is a reddit post I am interested in:

title: {title}

contents: {content}

Who is this person? What are they asking for? How does this post relate to the following need?

Need: {need}
"""


def summarize(post, need):
    try:
        post_content = post["selftext"] or "No content"
        completion = client.chat.completions.create(
            model="gpt-4-0613",
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant."},
                {
                    "role": "user",
                    "content": generate_summarize_message(
                        title=post["title"], content=post_content, need=need
                    ),
                },
            ],
            tools=summarize_tools,
            tool_choice={
                "type": "function",
                "function": {
                    "name": "summarize",
                },
            },
        )
        return json.loads(
            completion.choices[0].message.tool_calls[0].function.arguments
        )["summary"].strip()
    except:
        try:
            # If it failed because the post was too long, truncate it and try again.
            if len(post_content) > 4000:
                post_content = post_content[:4000]
                completion = client.chat.completions.create(
                    model="gpt-4-0613",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful AI assistant.",
                        },
                        {
                            "role": "user",
                            "content": generate_summarize_message(
                                title=post["title"], content=post_content, need=need
                            ),
                        },
                    ],
                    tools=summarize_tools,
                    tool_choice={
                        "type": "function",
                        "function": {
                            "name": "summarize",
                        },
                    },
                )
                return json.loads(
                    completion.choices[0].message.tool_calls[0].function.arguments
                )["summary"].strip()
        except:
            return None


discern_applicability_tools = [
    {
        "type": "function",
        "function": {
            "name": "discern_applicability",
            "description": "Determine if the person writing the post explicitly mentions having the given need.",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {
                        "type": "string",
                        "description": "The explanation for whether the person has the need or not.",
                    },
                    "applicable": {
                        "type": "boolean",
                        "description": "True if the person has the need, false otherwise.",
                    },
                },
                "required": ["explanation", "applicable"],
            },
        },
    }
]


def format_discern_applicability_messages(title, content, need):
    return [
        {"role": "system", "content": "You are a helpful AI assistant."},
        {
            "role": "user",
            "content": f"""
Here is the title and content of a reddit post I am interested in:

title: {title}
content: {content}

Does the person writing this post explicitly mention that they have the following need? {need}

Explain your reasoning before you answer. Answer true if the person has the need, or false otherwise. Label your true/false answer with \"Answer:\".
""",
        },
    ]


def discern_applicability(post, need):
    post_content = post["selftext"] or "No content"
    try:
        completion = client.chat.completions.create(
            model="gpt-4-0613",
            messages=format_discern_applicability_messages(
                post["title"], post_content, need
            ),
            tools=discern_applicability_tools,
            tool_choice={
                "type": "function",
                "function": {
                    "name": "discern_applicability",
                },
            },
        )
        applicability = json.loads(
            completion.choices[0].message.tool_calls[0].function.arguments
        )
    except:
        try:
            # If it failed because the post was too long, truncate it and try again.
            if len(post_content) > 4000:
                post_content = post_content[:4000]
                completion = client.chat.completions.create(
                    model="gpt-4-0613",
                    messages=format_discern_applicability_messages(
                        post["title"], post_content, need
                    ),
                    tools=discern_applicability_tools,
                    tool_choice={
                        "type": "function",
                        "function": {
                            "name": "discern_applicability",
                        },
                    },
                )
                applicability = json.loads(
                    completion.choices[0].message.tool_calls[0].function.arguments
                )
        except:
            return False
    # full_answer = davinci_llm(formatted_discern_applicability_prompt).strip()
    post["full_answer"] = applicability["explanation"]
    return applicability["applicable"]


score_post_relevance_tools = [
    {
        "type": "function",
        "function": {
            "name": "score_post_relevance",
            "description": "Score the relevance of the reddit post to the given need on a scale of 1 to 10.",
            "parameters": {
                "type": "object",
                "properties": {
                    "relevance_score": {
                        "type": "integer",
                        "description": "The relevance score between 1 and 10.",
                        "minimum": 1,
                        "maximum": 10,
                    },
                },
                "required": ["relevance_score"],
            },
        },
    }
]


def score_post_relevance(post, need):
    formatted_score_post_relevance_prompt = f"""
Here is the title and summary of a reddit post I am interested in:
title: {post["title"]}
summary: {post["summary"]}

On a scale of 1 to 10, how likely is it that the person writing this post has the following need? If you are not sure, make your best guess, or answer 1.

Need: {need}

Answer one integer between 1 and 10.
"""

    response = client.chat.completions.create(
        model="gpt-4-0613",
        messages=[
            {"role": "system", "content": "You are a helpful AI assistant."},
            {"role": "user", "content": formatted_score_post_relevance_prompt},
        ],
        tools=score_post_relevance_tools,
        tool_choice={
            "type": "function",
            "function": {
                "name": "score_post_relevance",
            },
        },
    )

    answer_relevance = json.loads(
        response.choices[0].message.tool_calls[0].function.arguments
    )["relevance_score"]

    return answer_relevance


score_subreddit_relevance_tools = [
    {
        "type": "function",
        "function": {
            "name": "score_subreddit_relevance",
            "description": "Score the relevance of the subreddit to the given need on a scale of 1 to 10.",
            "parameters": {
                "type": "object",
                "properties": {
                    "relevance_score": {
                        "type": "integer",
                        "description": "The relevance score between 1 and 10.",
                        "minimum": 1,
                        "maximum": 10,
                    },
                },
                "required": ["relevance_score"],
            },
        },
    }
]


@ray.remote
def score_subreddit_relevance(subreddit, need):
    client = OpenAI()

    formatted_score_subreddit_relevance_prompt = f"""
Here is a subreddit I am interested in: {subreddit["name"]}
Here is the description of the subreddit: {subreddit["description"]}

Please answer the following question. If you are not sure, answer 1:
On a scale of 1 to 10, how likely is it that anyone in this subreddit has the following need?

Need: {need}

Answer one integer between 1 and 10.
"""

    response = client.chat.completions.create(
        model="gpt-4-0613",
        messages=[
            {"role": "system", "content": "You are a helpful AI assistant."},
            {"role": "user", "content": formatted_score_subreddit_relevance_prompt},
        ],
        tools=score_subreddit_relevance_tools,
        tool_choice={
            "type": "function",
            "function": {
                "name": "score_subreddit_relevance",
            },
        },
    )

    # load into json
    relevance_score = json.loads(
        response.choices[0].message.tool_calls[0].function.arguments
    )["relevance_score"]

    print(subreddit["name"])
    print(subreddit["description"])
    print(relevance_score)

    subreddit["score"] = relevance_score
    return subreddit
