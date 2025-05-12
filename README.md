# Guess Who Game with OpenAI CLI

A Python command-line application that plays a "guess the character" game using OpenAI models. It reads a list of names from a text file, lets the model ask yes/no questions to identify a hidden target, and evaluates how efficiently the model splits the remaining possibilities at each step.

## Features

- Load a list of characters from a plain text file (`input_list.txt`).
- Choose a target name explicitly or at random.
- Use any supported OpenAI model for question generation (e.g. `gpt-3.5-turbo`, `gpt-4o-mini`).
- Stubbed or real oracle responses via OpenAI, answering `yes`, `no`, or `successful_guess` tags.
- Asynchronous calls for rapid batch evaluation of split performance.
- Tracks and plots:
  - **Deviation** of each question's yes/no split from the perfect 50/50 (ideal split = 0.50).
  - **Survivor count** (remaining candidates) on a secondary axis.
- Configurable maximum number of rounds and reasoning effort level (`low`/`medium`/`high`).

## Prerequisites

- Python 3.8 or higher
- An OpenAI API key with access to your chosen models

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/guess-who-questions.git
   cd guess-who-questions
   ```
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set your OpenAI API key:
   ```bash
   export OPENAI_API_KEY="sk-your-key-here"
   ```

## Input File Format

Create `input_list.txt` with one name per line, for example:
```
Frida Kahlo
Gabriel García Márquez
Leonardo DiCaprio
Beyoncé Knowles
Billie Jean King
Marie Curie
Ada Lovelace
Nelson Mandela
Aristotle
Steve Jobs
```

## Usage

```bash
python guess_name.py input_list.txt \
  --model gpt-3.5-turbo \
  --oracle-model o4-mini \
  --reasoning-effort low \
  --max-rounds 20 \
  --target-name "Steve Jobs"
```

- `input_list.txt`: path to the names file
- `--model`/`-m`: OpenAI model for generating questions
- `--oracle-model`/`-o`: model used to answer those questions
- `--reasoning-effort`/`-e`: reasoning effort level (`low`, `medium`, `high`)
- `--max-rounds`/`-n`: maximum yes/no iterations (default: 20)
- `--target-name`/`-t`: optional override for the hidden target (random if omitted)

After each question, the script:
1. Asks the main model to pose a yes/no question.
2. Uses the oracle model to answer for each surviving candidate.
3. Filters the candidate pool by the ground-truth answer.
4. Computes deviation from a perfect split and updates a plot.

At the end, you'll see an interactive Matplotlib chart showing:
- Deviation from 0.5 (left axis) per question
- Remaining survivors count (right axis)

## Development

- The CLI is built with [Typer](https://typer.tiangolo.com/).
- Async OpenAI calls via `openai.AsyncOpenAI` for parallel oracle evaluation.
- Plotting with [Matplotlib](https://matplotlib.org/).

## License

This project is released under the MIT License. Feel free to adapt and extend! 