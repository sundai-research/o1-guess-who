import os
from enum import Enum
from pathlib import Path
import random
import json
import re

import typer
import openai
import asyncio
from openai import AsyncOpenAI
import matplotlib.pyplot as plt


class OpenAIModel(str, Enum):
    GPT_3_5_TURBO = "gpt-3.5-turbo"
    GPT_4_TURBO = "gpt-4-turbo"
    GPT_4_TURBO_32K = "gpt-4-turbo-32k"
    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"
    # Reasoning (mini) models
    O3_MINI = "o3-mini"
    O4_MINI = "o4-mini"


class ReasoningEffort(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


app = typer.Typer()


@app.command()
def main(
    input_file: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to the input list file.",
    ),
    model: OpenAIModel = typer.Option(
        OpenAIModel.GPT_3_5_TURBO,
        "--model",
        "-m",
        help="OpenAI model to use for completions.",
    ),
    target_name: str = typer.Option(
        None,
        "--target-name",
        "-t",
        help="Name to guess (optional).",
    ),
    max_rounds: int = typer.Option(
        20,
        "--max-rounds",
        "-n",
        help="Maximum number of questions.",
    ),
    experiment_name: str = typer.Option(
        ..., "--experiment-name", "-x", help="Unique name for this experiment."
    ),
    oracle_model: OpenAIModel = typer.Option(
        OpenAIModel.GPT_4O,
        "--oracle-model",
        "-o",
        help="OpenAI model to use for oracle responses.",
    ),
    reasoning_effort: ReasoningEffort = typer.Option(
        ReasoningEffort.MEDIUM,
        "--reasoning-effort",
        "-e",
        case_sensitive=False,
        help="Reasoning effort level: low, medium, or high.",
    ),
) -> None:
    """
    Guess names based on an input list and OpenAI model.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        typer.secho(
            "Error: OPENAI_API_KEY environment variable is not set.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    openai.api_key = api_key

    # initialize async loop and client for faster oracle calls
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async_client = AsyncOpenAI(api_key=api_key)

    # Read names from file
    content = input_file.read_text(encoding="utf-8")
    names = [line.strip() for line in content.splitlines() if line.strip()]

    typer.secho(f"Using model: {model.value}", fg=typer.colors.GREEN)
    typer.secho(f"Loaded {len(names)} names.", fg=typer.colors.BLUE)

    # initialize survivor pool, deviation and survivors count tracking
    survivors = names.copy()
    deviations = []
    yes_counts = []
    no_counts = []
    survivors_counts = [len(survivors)]

    # select target character
    target = target_name if target_name else select_target_name(names)
    typer.secho(f"Target selected: {target}", fg=typer.colors.MAGENTA)

    # start guessing loop
    messages = [
        {"role": "system", "content": f"You are playing a guess-the-character game. Possible characters are: {', '.join(names)}. Ask yes/no questions to identify the character. You are in a competition with other players. Try to guess the character in the least number of questions possible."}
    ]

    # define async helper for oracle on a single candidate
    async def oracle_async(question: str, target: str, model: OpenAIModel, client: AsyncOpenAI) -> str:
        """
        Async oracle helper: evaluate question against a target character.
        """
        system_prompt = (
            "You are a reasoning oracle. Evaluate whether the target character fits the question. "
            "If the question is a direct guess of the character and correct, respond with <answer>successful_guess</answer>. "
            "If incorrect guess, respond with <answer>no</answer>. "
            "For yes/no questions, think step by step and respond with <answer>yes</answer> or <answer>no</answer>."
        )
        user_prompt = (
            f"Question to evaluate: {question}\n"
            f"Target character: {target}\n"
            "After reasoning, output only one of: <answer>yes</answer>, <answer>no</answer>, or <answer>successful_guess</answer>."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        response = await client.chat.completions.create(
            model=model.value,
            messages=messages,
            max_completion_tokens=20000,
        )
        reply = response.choices[0].message.content.strip()
        match = re.search(r"<answer>(yes|no|successful_guess)</answer>", reply, re.IGNORECASE)
        if match:
            return match.group(1).lower()
        low = reply.lower()
        if "successful_guess" in low:
            return "successful_guess"
        return "yes" if "yes" in low else "no"

    for idx in range(max_rounds):
        question = ask_model(messages, model, reasoning_effort)
        typer.secho(f"Model: {question}", fg=typer.colors.YELLOW)
        # use unified async oracle for ground truth
        answer = loop.run_until_complete(
            oracle_async(question, target, oracle_model, async_client)
        )
        typer.secho(f"Oracle: {answer}", fg=typer.colors.CYAN)
        messages.append({"role": "assistant", "content": question})
        messages.append({"role": "user", "content": answer})
        if answer == "successful_guess":
            typer.secho("Model guessed the character!", fg=typer.colors.GREEN)
            break
        # evaluate split factor among current survivors asynchronously
        results_list = loop.run_until_complete(
            asyncio.gather(*(
                oracle_async(question, cand, oracle_model, async_client)
                for cand in survivors
            ))
        )
        yes_count = results_list.count("yes")
        no_count = results_list.count("no")
        yes_counts.append(yes_count)
        no_counts.append(no_count)
        results = dict(zip(survivors, results_list))
        survivors = [c for c, res in results.items() if res == answer]
        survivors_counts.append(len(survivors))
        # compute deviation from perfect split (0.5)
        total = yes_count + no_count
        split = yes_count / total if total else 0
        deviation = abs(split - 0.5)
        deviations.append(deviation)
        typer.secho(
            f"After Q{idx+1}: yes={yes_count}, no={no_count}, ground_truth={answer}",
            fg=typer.colors.MAGENTA,
        )
    typer.secho("Max questions reached. Game over.", fg=typer.colors.RED)

    # save results to JSONL
    exp_dir = Path("experiments") / experiment_name
    exp_dir.mkdir(parents=True, exist_ok=True)
    params = {
        "input_file": str(input_file),
        "model": model.value,
        "oracle_model": oracle_model.value,
        "reasoning_effort": reasoning_effort.value,
        "max_rounds": max_rounds,
        "target_name": target_name,
    }
    (exp_dir / "params.json").write_text(json.dumps(params, indent=2))

    records_file = exp_dir / "results.jsonl"
    with records_file.open("w", encoding="utf-8") as f:
        for i, deviation in enumerate(deviations, start=1):
            record = {
                "question_number": i,
                "yes_count": yes_counts[i-1],
                "no_count": no_counts[i-1],
                "survivors_count": survivors_counts[i-1],
                "deviation": deviation,
            }
            f.write(json.dumps(record) + "\n")

def select_target_name(names: list[str]) -> str:
    return random.choice(names)

def ask_model(messages: list[dict], model: OpenAIModel, reasoning_effort: ReasoningEffort) -> str:
    # Send request with unified parameters
    response = openai.chat.completions.create(
        model=model.value,
        messages=messages,
        max_completion_tokens=30000,
        reasoning_effort=reasoning_effort.value,
    )
    return response.choices[0].message.content

if __name__ == "__main__":
    app()
