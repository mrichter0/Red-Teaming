from typing import List, Optional
from pydantic import BaseModel
from fastmcp import FastMCP

RECORDS = [
    {"id": "doc1", "title": "First doc", "text": "Hello world."},
    {"id": "doc2", "title": "Second doc", "text": "More content."},
]
LOOKUP = {r["id"]: r for r in RECORDS}

mcp = FastMCP(name="MCP", instructions="Demo Deep‑Research server.")

class SearchHit(BaseModel):
    id: str
    title: str
    text: str
    url: Optional[str] = None

class SearchResults(BaseModel):
    results: List[SearchHit]

@mcp.tool()  # no output_schema parameter
async def search(query: str) -> SearchResults:
    """
    Perform a keyword search and return matching documents.
    """
    q = query.lower()
    hits = [
        SearchHit(
            id=r["id"],
            title=r["title"],
            text=r["text"][:160],
            url=None,       # include url even if None to satisfy the spec
        )
        for r in RECORDS
        if q in r["title"].lower() or q in r["text"].lower()
    ]
    return SearchResults(results=hits)

class Document(BaseModel):
    id: str
    title: str
    text: str
    url: Optional[str] = None

@mcp.tool()
async def fetch(id: str) -> Document:
    """
    Retrieve the full document by ID.
    """
    if id not in LOOKUP:
        raise ValueError("unknown id")
    rec = LOOKUP[id]
    return Document(id=rec["id"], title=rec["title"], text=rec["text"], url=None)

if __name__ == "__main__":
    # SSE transport on /sse/, as requested
    mcp.run(transport="http", host="0.0.0.0", port=5000, path="/sse/")

