# nmt-fastapi-a2a

This codebase implements an agent-to-agent (A2A) orchestration system using FastAPI, and `nmt-fastapi-library`. It is focused on demonstrating how to route user queries to specialized agents. The main entrypoint is the `DirectorAgent`, which streams responses and delegates tasks to other agents (e.g., `WidgetsAgent`) based on query analysis.

## Installation

To set up your development environment, follow these steps:

### Prerequisites

- Python 3.11+

### Prepare Development Environment

Clone the repository and install dependencies using Poetry:

```bash
git clone https://github.com/not-mt/nmt-fastapi-a2a.git
cd nmt-fastapi-a2a
```

Create a virtual environment and install Poetry:

```bash
test -d .venv || python -m venv .venv
source .venv/Scripts/activate
pip install poetry
cp samples/poetry.toml .
```

Install dependencies:

```bash
poetry install
```

Install pre-commit:

```bash
pre-commit install
```

### OPTIONAL: VS Code (on Windows)

If you are developing on Windows and have a bash shell available, copy samples:

```bash
cp -urv samples/{.local,.vscode,*} .
```

Customize `.local/activate.env` and other files as needed.

**NOTE:** You can update `PROJECTS` in `.local/activate.env` file manually, or you can use this command to update it for you. This will set the value to the parent directory of your current directory:

```bash
# get the parent directory, and replace /c/path with C:/path
rpd=$(dirname "$(pwd)" | sed -E 's|^/([a-z])|\U\1:|')
sed \
  -e 's|# export PROJECTS=".*FIXME.*$|export PROJECTS="'"$rpd"'"|' \
  -i .local/activate.env
```

Test the activate script:

```bash
source .local/activate.env
```

## Usage

How to run the application, including example commands and configuration details.

### Configuration

This service is configured using YAML configuration files. You may copy the `nmtfast-config-default.yaml` and update as necessary:

```bash
cp nmtfast-config-default.yaml nmtfast-config-local.yaml
$EDITOR nmtfast-config-local.yaml
```

This is an example configuration:

```yaml
version: 1

a2a:
  director_url: http://localhost:10010
  director:
    host: localhost
    port: 10010
    agents:
      widgets: http://localhost:10020
  agents:
    widgets:
      host: localhost
      port: 10020
      mcp_url: http://localhost:8001/mcp/
  llm_provider:
    name: ollama/deepseek-r1:8b
    base_url: http://localhost:11434/v1

logging:
  level: DEBUG
  loggers:
    "httpcore":
      level: INFO
    "a2a.utils":
      level: INFO
    "a2a.server":
      level: INFO
    "sse_starlette.sse":
      level: INFO
```


### Running the Service

You may run the service using a command like this:

```bash
export APP_CONFIG_FILES="nmtfast-config-default,nmtfast-config-local.yaml"
poetry run uvicorn app.main:app --reload
```

**OPTIONAL:** If Docker is available, you may run the service like this:

```bash
cp samples/docker-compose.yaml .
docker-compose build
docker-compose up
```

## Contributing

Contributions are welcome! Please submit a pull request or open an issue.

## License

This project is licensed under the [MIT License](LICENSE).
