"""Recover usable JSON from a possibly-truncated LLM completion.

If the model's output got cut off mid-string (hit max_tokens), a plain
json.loads throws immediately even though the payload is mostly complete.
This finds the longest prefix that ends on a clean value boundary, closes
any open strings/objects/arrays, and parses that -- recovering every
complete item and dropping only the truncated tail.
"""
import json


def parse_lenient(text: str) -> tuple[dict, bool]:
    """Returns (parsed_object, was_truncated)."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[: -3]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        return json.loads(text), False
    except json.JSONDecodeError:
        pass

    # Walk the string tracking nesting depth; remember the last index where
    # we were sitting at a clean boundary (just after a closed value, comma,
    # or bracket) outside of any string.
    depth_stack: list[str] = []
    in_string = False
    escape = False
    last_clean_index = 0

    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
                last_clean_index = i + 1
            continue

        if ch == '"':
            in_string = True
        elif ch in "{[":
            depth_stack.append(ch)
        elif ch in "}]":
            if depth_stack:
                depth_stack.pop()
            last_clean_index = i + 1
        elif ch == ",":
            last_clean_index = i  # trailing comma will be stripped below

    prefix = text[:last_clean_index].rstrip()
    prefix = prefix.rstrip(",")

    # Close any structures still open.
    closer = "".join("}" if c == "{" else "]" for c in reversed(depth_stack))
    candidate = prefix + closer

    try:
        return json.loads(candidate), True
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not salvage JSON from model output: {exc}") from exc
