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


# ---------------------------------------------------------------------------
# Binding declaration parser
# ---------------------------------------------------------------------------
# Syntax (at any place in the file, but conventionally at the top):
#   binding $var_name  type  [default_value]
#
# Supported types: boolean, slider, number, string
# Optional default: single token after type (unquoted for numbers, quoted for strings)
#
# Returns a list of dicts: {name, type, default}

def parse_bindings(script: str) -> list[dict]:
    """Scan a DSL script and return all `binding` declarations."""
    VALID_TYPES = {"boolean", "slider", "number", "string"}
    result: list[dict] = []
    for raw in script.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        toks = _tokenize(stripped)
        if not toks or toks[0].lower() != "binding":
            continue
        if len(toks) < 3:
            continue
        var_tok = toks[1]  # e.g. $slide_offset
        type_tok = toks[2].lower()
        if not var_tok.startswith("$"):
            continue
        if type_tok not in VALID_TYPES:
            continue
        name = var_tok[1:]  # strip leading $
        # optional default
        default = None
        if len(toks) >= 4:
            raw_default = toks[3]
            # strip quotes for string defaults
            if (raw_default.startswith("'") and raw_default.endswith("'")) or \
               (raw_default.startswith('"') and raw_default.endswith('"')):
                default = raw_default[1:-1]
            else:
                default = raw_default
        result.append({"name": name, "type": type_tok, "default": default})
    return result
