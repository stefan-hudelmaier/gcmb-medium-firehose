# Medium Publisher

This project is a Python-based application for receiving Medium articles. It publishes data via [gmcb.io](https://gcmb.io).
The gcmb project where you can find the data can be found [here](https://gcmb.io/medium/medium-firehose)

## Setup
1. Clone the repository.
2. ```uv sync```
3. Copy `.env.example` to `.env` and configure your environment variables.

## Usage
- Run the main application:
  ```bash
  uv run main.py
  ```
- Use provided scripts and configuration files to customize publishing workflows.

## License
This project is provided under the MIT License.
