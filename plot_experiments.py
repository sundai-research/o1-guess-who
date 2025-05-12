import json
from pathlib import Path
from typing import List

import typer
import matplotlib.pyplot as plt
from itertools import cycle
import seaborn as sns
from matplotlib.lines import Line2D

app = typer.Typer()

# choose a seaborn style that exists in current Matplotlib version
preferred_styles = [
    'seaborn-whitegrid',
    'seaborn-v0_8-whitegrid',  # Matplotlib 3.8+ naming
]
for _style in preferred_styles:
    if _style in plt.style.available:
        plt.style.use(_style)
        break

@app.command()
def plot(
    experiments: List[str] = typer.Argument(..., help="Names of experiments to plot"),
    experiments_dir: Path = typer.Option(
        Path("experiments"), "--dir", "-d", help="Directory containing experiment subfolders"
    ),
    output: Path = typer.Option(
        None, "--output", "-o", help="File path to save the combined plot (PNG format)"
    ),
) -> None:
    """
    Plot deviation and survivor count for multiple experiments.
    Each experiment should exist under EXPERIMENTS_DIR/EXPERIMENT_NAME with params.json and results.jsonl.
    """
    # create figure and twin axis
    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax2 = ax1.twinx()
    # prepare distinct colors
    color_cycler = cycle(sns.color_palette("tab10"))
    legend_lines = []
    legend_labels = []
    # iterate experiments
    for exp in experiments:
        exp_path = experiments_dir / exp
        if not exp_path.exists():
            typer.secho(f"Experiment directory not found: {exp_path}", fg=typer.colors.RED)
            raise typer.Exit(1)
        # load params for label
        params_file = exp_path / "params.json"
        if not params_file.exists():
            label = exp
        else:
            params = json.loads(params_file.read_text(encoding='utf-8'))
            label = f"{exp} ({params.get('model')}, eff={params.get('reasoning_effort')})"
        # read results
        results_file = exp_path / "results.jsonl"
        if not results_file.exists():
            typer.secho(f"Results file not found: {results_file}", fg=typer.colors.RED)
            raise typer.Exit(1)
        q_nums, deviations, survivors = [], [], []
        for line in results_file.read_text(encoding='utf-8').splitlines():
            record = json.loads(line)
            q_nums.append(record.get("question_number"))
            deviations.append(record.get("deviation"))
            survivors.append(record.get("survivors_count"))
        color = next(color_cycler)
        # deviation solid
        dev_line, = ax1.plot(
            q_nums,
            deviations,
            color=color,
            marker='o',
            linewidth=2,
        )
        # survivors dashed on twin axis
        ax2.plot(
            q_nums,
            survivors,
            color=color,
            linestyle='--',
            marker='s',
            linewidth=1.5,
        )
        legend_lines.append(dev_line)
        legend_labels.append(label)
    # axis styling
    ax1.axhline(0, color='gray', linestyle='--', linewidth=1)
    ax1.set_xlabel('Question Number', fontsize=12)
    ax1.set_ylabel('Abs Deviation from 0.50', color='tab:blue', fontsize=12)
    ax2.set_ylabel('Survivor Count', color='tab:orange', fontsize=12)
    ax1.tick_params(axis='y', labelcolor='tab:blue')
    ax2.tick_params(axis='y', labelcolor='tab:orange')
    ax1.grid(True, linestyle='--', linewidth=0.5, alpha=0.7)
    # legend for experiments (color groups)
    exp_legend = ax1.legend(
        legend_lines,
        legend_labels,
        loc='upper center',
        bbox_to_anchor=(0.5, -0.12),
        ncol=2,
        fontsize=10,
        frameon=True,
        fancybox=True,
    )
    # add metric legend (line style meaning)
    metric_handles = [
        Line2D([0], [0], color='grey', marker='o', linewidth=2, label='Deviation (solid)'),
        Line2D([0], [0], color='grey', linestyle='--', marker='s', linewidth=1.5, label='Survivor Count (dashed)'),
    ]
    ax1.legend(
        handles=metric_handles,
        loc='upper left',
        fontsize=9,
        frameon=True,
    )
    # add experiments legend back
    ax1.add_artist(exp_legend)
    plt.title('Experimental Comparison: Deviation & Survivors', fontsize=14)
    fig.tight_layout(rect=[0, 0.15, 1, 1])
    # output
    if output:
        fig.savefig(output, dpi=300)
        typer.secho(f"Plot saved to {output}", fg=typer.colors.GREEN)
    else:
        plt.show()

if __name__ == '__main__':
    app() 