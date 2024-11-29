"""Utility functions."""

import re


def split_text_min_chunks(text: str, max_length=32):
    """Logic to split text in 32 words max based on !, ? and ."""
    # Split the text into sentences based on punctuation
    sentences = re.split(r"(?<=[.!?])\s*", text)

    results = []
    current_chunk = ""

    for sentence in sentences:
        # Check if adding the sentence to the current chunk stays within the limit
        if len(current_chunk) + len(sentence) + 1 <= max_length:  # +1 for space
            if current_chunk:
                current_chunk += " " + sentence
            else:
                current_chunk = sentence
        else:
            # If the current chunk is full, add it to results and start a new chunk
            if current_chunk:
                results.append(current_chunk.strip())
            current_chunk = sentence

    # Add the last chunk if there's anything left
    if current_chunk:
        results.append(current_chunk.strip())

    return results
