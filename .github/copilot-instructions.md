# Copilot Instructions for AI Coding Agents

## Project Overview
This codebase implements an agent-to-agent (A2A) orchestration system using FastAPI, focused on routing user queries to specialized agents. The main entrypoint is the DirectorAgent, which streams responses and delegates tasks to other agents (e.g., WidgetsAgent) based on query analysis.

## Architecture & Key Components
- **src/app/director.py**: Entrypoint for running the DirectorAgent server. Uses Uvicorn, Click, and Starlette. The DirectorAgentExecutor is instantiated here.
- **src/agents/director/agent.py**: Implements DirectorAgent, which selects and routes queries to agents. Uses LLMs via the `instructor` library for agent selection.
- **src/agents/director/agent_executor.py**: Handles streaming, event queue updates, and task lifecycle for DirectorAgent.
- **src/app/settings.py**: Centralized configuration using Pydantic models. Defines settings for agents, LLM providers, and service URLs.
- **src/agents/widgets/**: Example of a specialized agent implementation (WidgetsAgent).
- **src/app/web/templates/**: Contains HTML templates for chat UI.

## Developer Workflows
- **Run the DirectorAgent server:**
  ```bash
  python src/app/director.py --host <host> --port <port>
  ```
- **Configuration:**
  - Uses YAML config files (`nmtfast-config-default.yaml`, `nmtfast-config-local.yaml`).
  - Settings are loaded via `get_app_settings()` in `src/app/settings.py`.
- **Streaming Responses:**
  - All agent communication is designed to be streamed (see `DirectorAgent.stream`). Synchronous invocation is not supported.
- **Agent Selection:**
  - The DirectorAgent uses an LLM (configurable in settings) to select the target agent for each query. Only agent IDs defined in settings are valid.
- **Adding New Agents:**
  - Register new agents in `src/app/settings.py` and update the agent selection logic in `DirectorAgent._select_agent`.

## Patterns & Conventions
- **Event-Driven:**
  - Task and message updates are handled via event queues (`EventQueue`, `TaskStatusUpdateEvent`).
- **Streaming Only:**
  - All agent responses must use the streaming API. Synchronous methods raise `NotImplementedError`.
- **OAuth Token Context:**
  - Use `OAUTH_TOKEN_CTX` for passing authentication tokens between agents.
- **Content Types:**
  - Supported content types are defined in `DirectorAgent.SUPPORTED_CONTENT_TYPES`.
- **Logging:**
  - Logging is configured via `configure_logging(settings)` in `src/app/director.py`.

## Integration Points
- **LLM Provider:**
  - Configured via `LLMProviderSettings` in `src/app/settings.py`. Supports OpenAI, Ollama, etc.
- **Agent-to-Agent Communication:**
  - Uses HTTPX async clients for inter-agent calls.
- **Web UI:**
  - Chat interface in `src/app/web/templates/chat.html`.

## Examples
- **Routing a query:**
  - "What is the force of widget ID 1?" → Routed to WidgetsAgent.
- **Streaming response:**
  - `DirectorAgent.stream(query, sessionId)` yields progress and final results.

## References
- `src/app/director.py`, `src/agents/director/agent.py`, `src/app/settings.py`, `src/agents/widgets/`, `src/app/web/templates/chat.html`

---
