# decline-code-assistant

Agent that explains why card transactions were declined and what a merchant or
payments-ops team should do next, grounded in a curated knowledge base of
ISO 8583 response codes, scheme decline groups, 3-D Secure outcomes and retry
policies.

Built with LangGraph and the Anthropic Python SDK; ships as a CLI (`declines`)
and an MCP server (`declines-mcp`).
