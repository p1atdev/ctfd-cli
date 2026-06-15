# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx>=0.28.1,<1",
#     "pydantic>=2.12,<3",
#     "pydantic-settings>=2.12,<3",
#     "rich>=14.2,<15",
#     "typer>=0.21,<1",
# ]
# ///

from ctfd.cli import app

app(prog_name="ctfd")
