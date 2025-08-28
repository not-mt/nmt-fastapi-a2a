"""Smoke tests to ensure AgentExecutor __init__ assigns agent instances."""


def test_director_executor_init(monkeypatch):
    """Instantiating DirectorAgentExecutor should create the agent attribute."""

    class DummyDirector:
        instantiated = False

        def __init__(self, settings):
            DummyDirector.instantiated = True

    monkeypatch.setattr(
        "app.agents.director.agent_executor.DirectorAgent",
        DummyDirector,
    )

    from app.agents.director.agent_executor import DirectorAgentExecutor
    from app.settings import AppSettings

    exec = DirectorAgentExecutor(AppSettings())
    assert getattr(exec, "agent", None) is not None
    assert DummyDirector.instantiated


def test_widgets_executor_init(monkeypatch):
    """Instantiating MCPAgentExecutor should create the agent attribute."""

    class DummyWidgetAgent:
        instantiated = False

        def __init__(self, settings):
            DummyWidgetAgent.instantiated = True

    monkeypatch.setattr(
        "app.agents.widgets.agent_executor.WidgetsMCPAgent",
        DummyWidgetAgent,
    )

    from app.agents.widgets.agent_executor import MCPAgentExecutor
    from app.settings import AppSettings

    exec = MCPAgentExecutor(AppSettings())
    assert getattr(exec, "agent", None) is not None
    assert DummyWidgetAgent.instantiated
