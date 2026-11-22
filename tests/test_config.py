from memograph.core.config import Settings


def test_settings_load_with_defaults():
    s = Settings(_env_file=None)
    assert s.llm_provider == "ollama"
    assert "asyncpg" in s.database_url
