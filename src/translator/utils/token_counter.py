"""Token counting and text chunking utilities."""

from typing import List
import tiktoken


def num_tokens_from_string(string: str, encoding_name: str) -> int:
    """Count the number of tokens in a string."""
    encoding = tiktoken.get_encoding(encoding_name)
    return len(encoding.encode(string))


def split_chapter(chapter: str, max_tokens: int) -> List[str]:
    """Split a chapter into chunks based on token count."""
    chunks = []
    lines = chapter.split('\n')
    current_chunk = ""

    for line in lines:
        chunk_tokens = num_tokens_from_string(current_chunk + line + '\n', 'cl100k_base')
        if chunk_tokens > max_tokens:
            chunks.append(current_chunk.strip())
            current_chunk = line + '\n'
        else:
            current_chunk += line + '\n'

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks
