"""CLI entrypoint for CRIRA."""

from crira.pipeline.orchestrator import run_dataset_pipeline


if __name__ == "__main__":
    result = run_dataset_pipeline(input_path="data/reviews.json", output_dir="outputs")
    print(result)
