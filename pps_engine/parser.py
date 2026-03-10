from .exceptions import DSLError

def _tokenize(line: str) -> list[str]:
    tokens = []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch in (" ", "\t", "(", ")", ",", "{"):
            i += 1
            continue
        if ch == "}":
            tokens.append("}")
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            try:
                j = line.index(quote, i + 1) + 1
            except ValueError:
                j = len(line)
            tokens.append(line[i:j])
            i = j
        else:
            j = i
            while j < len(line) and line[j] not in (" ", "\t", "(", ")", ",", "{", "}"):
                j += 1
            tokens.append(line[i:j])
            i = j
    return tokens

def _find_matching_end(lines: list[str], start: int) -> int:
    depth = 0
    for i in range(start, len(lines)):
        toks = _tokenize(lines[i])
        if not toks:
            continue
        tok0 = toks[0].lower()
        if tok0 in ("loop", "if", "do", "function", "def"):
            depth += 1
        elif tok0 in ("end", "until", "}"):
            if tok0 == "}" and len(toks) > 1 and toks[1].lower() in ("elif", "else"):
                # `} elif` and `} else` just continues the block, depth does not change
                pass
            else:
                depth -= 1
                if depth == 0:
                    return i
    raise DSLError(f"Missing 'end' or '}}' for block starting at line {start + 1}")

def _find_matching_until(lines: list[str], start: int) -> int:
    depth = 0
    for i in range(start, len(lines)):
        toks = _tokenize(lines[i])
        if not toks:
            continue
        tok0 = toks[0].lower()
        if tok0 in ("loop", "if", "do", "function", "def"):
            depth += 1
        elif tok0 in ("end", "until", "}"):
            depth -= 1
            if depth == 0:
                if tok0 == "}" and len(toks) > 1 and toks[1].lower() == "until":
                    return i
                if tok0 != "until":
                    raise DSLError(f"Expected 'until' for 'do' at line {start + 1}, got '{tok0}' at line {i + 1}")
                return i
    raise DSLError(f"Missing 'until' for 'do' at line {start + 1}")
