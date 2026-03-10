import threading
import time
import random
from pathlib import Path
from typing import Callable, Optional
import numpy as np
import re

from screenshot import WindowCapture
from .exceptions import DSLError, BreakLoop, ContinueLoop, ReturnFunc
from .window import WindowMixin
from .vision import VisionMixin
from .parser import _tokenize, _find_matching_end, _find_matching_until

class DSLEngine(WindowMixin, VisionMixin):
    """Thông dịch và chạy DSL script."""

    def __init__(self):
        self._capture: Optional[WindowCapture] = None
        self._last_frame: Optional[np.ndarray] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._variables: dict[str, float] = {}
        self._images_dir = Path("images")
        self._reference_size: tuple[int, int] = (1920, 1080)
        self._prev_gray_roi: Optional[np.ndarray] = None
        self._functions: dict[str, tuple[list[str], int, int]] = {}

    def set_capture(self, capture: Optional[WindowCapture]):
        with self._lock:
            self._capture = capture

    def set_last_frame(self, frame: np.ndarray):
        with self._lock:
            self._last_frame = frame.copy()

    def request_stop(self):
        self._stop_event.set()

    def reset_stop(self):
        self._stop_event.clear()

    def _get_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            if self._last_frame is not None:
                return self._last_frame.copy()
        with self._lock:
            cap = self._capture
        if cap:
            return cap.capture()
        return None

    @staticmethod
    def _parse_lines(script: str) -> list[str]:
        lines = []
        for raw in script.splitlines():
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            lines.append(stripped)
        return lines

    @staticmethod
    def _parse_string_arg(token: str) -> str:
        if (token.startswith("'") and token.endswith("'")) or \
           (token.startswith('"') and token.endswith('"')):
            return token[1:-1]
        return token

    def execute(self, script: str, log_fn: Optional[Callable[[str], None]] = None):
        self._variables.clear()
        self._prev_gray_roi = None
        self._script_lines = self._parse_lines(script)
        lines = self._script_lines
        self._labels: dict[str, int] = {}
        self._functions.clear()
        
        # Pre-scan for labels and functions
        idx = 0
        while idx < len(lines):
            ln = lines[idx].strip()
            if not ln or ln.startswith("#"):
                idx += 1
                continue
            
            if ln.endswith(":"):
                label_name = ln[:-1].strip()
                self._labels[label_name] = idx
            else:
                toks = _tokenize(ln)
                if toks and toks[0].lower() in ("function", "def"):
                    func_name = toks[1]
                    arg_names = toks[2:]
                    
                    # Need to find the end block of the function to skip scanning inner labels occasionally
                    # but _find_matching_end requires proper context, let's just find where the function ends
                    block_end = _find_matching_end(self._script_lines, idx)
                    self._functions[func_name] = (arg_names, idx + 1, block_end)
                    idx = block_end
            idx += 1
            
        self._exec_block(self._script_lines, 0, len(self._script_lines), log_fn)

    def _exec_block(self, lines: list[str], start: int, end: int,
                    log_fn: Optional[Callable[[str], None]]) -> int:
        i = start
        while i < end:
            if self._stop_event.is_set():
                return end
            line = lines[i]
            tokens = _tokenize(line)
            if not tokens:
                i += 1
                continue
            cmd = tokens[0].lower()

            if cmd == "click":
                x = int(self._resolve_value(tokens[1]))
                y = int(self._resolve_value(tokens[2]))
                self._window_click(x, y)
                if log_fn: log_fn(f"click {x} {y}")
            elif cmd == "rclick":
                x = int(self._resolve_value(tokens[1]))
                y = int(self._resolve_value(tokens[2]))
                self._window_click(x, y, button="right")
            elif cmd == "dclick":
                x = int(self._resolve_value(tokens[1]))
                y = int(self._resolve_value(tokens[2]))
                self._window_click(x, y, double=True)
            elif cmd == "move":
                x = int(self._resolve_value(tokens[1]))
                y = int(self._resolve_value(tokens[2]))
                self._window_move(x, y)
            elif cmd == "drag":
                self._window_drag(
                    int(self._resolve_value(tokens[1])),
                    int(self._resolve_value(tokens[2])),
                    int(self._resolve_value(tokens[3])),
                    int(self._resolve_value(tokens[4])),
                )
            elif cmd in ("drag_to", "drag_image"):
                img1 = self._parse_string_arg(tokens[1])
                img2 = self._parse_string_arg(tokens[2])
                thresh = float(tokens[3]) if len(tokens) > 3 else 0.8
                pos1 = self._find_template(img1, thresh)
                pos2 = self._find_template(img2, thresh) if pos1 else None
                if pos1 and pos2:
                    self._window_drag(pos1[0], pos1[1], pos2[0], pos2[1])
                    if log_fn: log_fn(f"drag {img1}@{pos1} -> {img2}@{pos2}")
                else:
                    if log_fn: log_fn(f"drag_to failed: {img1} or {img2} not found")
            elif cmd == "drag_offset":
                img = self._parse_string_arg(tokens[1])
                dx = int(self._resolve_value(tokens[2]))
                dy = int(self._resolve_value(tokens[3]))
                pos = self._find_template(img)
                if pos is not None:
                    start_x, start_y = pos
                    end_x = start_x + dx
                    end_y = start_y + dy
                    self._window_drag(start_x, start_y, end_x, end_y)
                    if log_fn: log_fn(f"drag_offset {img} center+({dx},{dy})")
                else:
                    if log_fn: log_fn(f"drag_offset failed: image not found")
            elif cmd == "scroll":
                amount = int(self._resolve_value(tokens[1]))
                self._window_scroll(amount)
                if log_fn: log_fn(f"scroll {amount}")
            elif cmd == "key":
                self._window_key(tokens[1])
            elif cmd == "type":
                text = self._parse_string_arg(tokens[1])
                self._window_type_text(text)
            elif cmd == "count":
                var = tokens[1]
                img = self._parse_string_arg(tokens[2])
                thresh = float(self._resolve_value(tokens[3])) if len(tokens) > 3 else 0.8
                n = self._count_template(img, thresh)
                self._variables[var] = float(n)
                if log_fn: log_fn(f"count {img} = {n}")
            elif cmd == "wait":
                secs = self._resolve_value(tokens[1])
                self._interruptible_sleep(secs)
            elif cmd == "wait_random":
                lo = float(self._resolve_value(tokens[1]))
                hi = float(self._resolve_value(tokens[2]))
                self._interruptible_sleep(random.uniform(lo, hi))
            elif cmd == "log":
                if len(tokens) > 1:
                    msgs = []
                    for arg in tokens[1:]:
                        if (arg.startswith("'") and arg.endswith("'")) or (arg.startswith('"') and arg.endswith('"')):
                            msgs.append(self._parse_string_arg(arg))
                        else:
                            val = self._resolve_value(arg)
                            # if it's a float that represents an integer, print as int
                            if isinstance(val, float) and val.is_integer():
                                msgs.append(str(int(val)))
                            else:
                                msgs.append(str(val))
                    msg = "".join(msgs)
                else:
                    msg = ""
                if log_fn: log_fn(msg)
            elif cmd == "find_and_click_largest_shiki":
                thresh_val = int(self._resolve_value(tokens[1])) if len(tokens) > 1 else 50
                pos = self._find_largest_shiki(dark_thresh=thresh_val)
                if pos:
                    self._window_click(pos[0], pos[1])
                    if log_fn: log_fn(f"clicked largest shiki at {pos}")
                else:
                    if log_fn: log_fn("no shiki silhouette found")
            elif cmd == "throw_at_largest_shiki":
                delay = int(self._resolve_value(tokens[1])) if len(tokens) > 1 else 100
                mt = int(self._resolve_value(tokens[2])) if len(tokens) > 2 else 30
                pos = self._find_largest_moving(delay_ms=delay, motion_thresh=mt)
                if pos:
                    self._window_click(pos[0], pos[1])
                    if log_fn: log_fn(f"threw at moving shiki at {pos}")
                else:
                    if log_fn: log_fn("no moving shiki detected")
            elif cmd == "find_and_click":
                images, thresh = self._parse_find_args(tokens[1:])
                for img in images:
                    pos = self._find_template(img, thresh)
                    if pos:
                        self._window_click(pos[0], pos[1])
                        if log_fn: log_fn(f"found & clicked {img} at {pos}")
                        break
                else:
                    if log_fn: 
                        names = ", ".join(images)
                        log_fn(f"not found: [{names}]")
            elif cmd == "wait_for":
                images, timeout = self._parse_wait_args(tokens[1:])
                self._wait_for_images(images, timeout, log_fn)
            elif cmd == "wait_and_click":
                images, timeout = self._parse_wait_args(tokens[1:])
                result = self._wait_for_images(images, timeout, log_fn)
                if result:
                    self._window_click(result[1][0], result[1][1])
            elif cmd == "resize":
                rw = int(self._resolve_value(tokens[1])) if len(tokens) > 1 else 1920
                rh = int(self._resolve_value(tokens[2])) if len(tokens) > 2 else 1080
                self.resize_window(rw, rh)
                if log_fn: log_fn(f"resize window to {rw}x{rh}")
            elif cmd == "set":
                self._handle_set(tokens)
            elif cmd == "do":
                block_end = _find_matching_until(lines, i)
                cond_line = lines[block_end].strip()
                m = re.match(r'^(?:\}\s*)?until\s+(.*?)\s*\{?$', cond_line, re.IGNORECASE)
                expr_str = m.group(1).strip() if m else ""
                
                until_tokens = _tokenize(cond_line)
                if until_tokens and until_tokens[0] == "}":
                    condition_tokens = until_tokens[2:]
                else:
                    condition_tokens = until_tokens[1:]
                while not self._stop_event.is_set():
                    try:
                        self._exec_block(lines, i + 1, block_end, log_fn)
                    except BreakLoop:
                        break
                    except ContinueLoop:
                        pass
                    if self._eval_condition(condition_tokens, expr_str):
                        break
                    time.sleep(0.01)
                i = block_end + 1
                continue
            elif cmd in ("until", "}"):
                pass
            elif cmd == "loop":
                block_end = _find_matching_end(lines, i)
                count_token = tokens[1].lower() if len(tokens) > 1 else "forever"
                if count_token == "forever":
                    while not self._stop_event.is_set():
                        try:
                            self._exec_block(lines, i + 1, block_end, log_fn)
                        except BreakLoop:
                            break
                        except ContinueLoop:
                            pass
                        time.sleep(0.01)
                else:
                    n = int(self._resolve_value(count_token))
                    for _ in range(n):
                        if self._stop_event.is_set():
                            break
                        try:
                            self._exec_block(lines, i + 1, block_end, log_fn)
                        except BreakLoop:
                            break
                        except ContinueLoop:
                            pass
                        time.sleep(0.01)
                i = block_end + 1
                continue
            elif cmd in ("function", "def"):
                # Functions are loaded during prescan, skip execution
                block_end = _find_matching_end(lines, i)
                i = block_end + 1
                continue
            elif cmd == "if":
                i = self._handle_if(lines, i, end, log_fn)
                continue
            elif cmd in ("end", "else", "elif", "}"):
                pass
            elif cmd == "break":
                if log_fn: log_fn("break")
                raise BreakLoop()
            elif cmd == "continue":
                if log_fn: log_fn("continue")
                raise ContinueLoop()
            elif cmd == "goto":
                label = tokens[1] if len(tokens) > 1 else ""
                if label in self._labels:
                    if log_fn: log_fn(f"goto {label}")
                    i = self._labels[label]
                    continue
                else:
                    if log_fn: log_fn(f"Label not found: {label}")
            elif cmd == "return":
                if len(tokens) > 1:
                    expr = " ".join(tokens[1:])
                    val = self._eval_expr(expr)
                else:
                    val = 0.0
                if log_fn: log_fn(f"return {val}")
                try:
                    raise ReturnFunc(float(val))
                except Exception:
                    raise ReturnFunc(val)
            elif cmd in self._functions:
                # Execute a user defined function as a statement
                arg_vals = []
                for idx_arg in range(len(self._functions[cmd][0])):
                    if idx_arg + 1 < len(tokens):
                        arg_vals.append(float(self._resolve_value(tokens[idx_arg + 1])))
                    else:
                        arg_vals.append(0.0)
                self._execute_function(cmd, arg_vals, log_fn)
                
            elif line.endswith(":"):
                pass
            elif "=" in line:
                m = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*(\+|-|\*|/|%|\*\*)?=\s*(.*)$', line.strip())
                if m:
                    var, op_prefix, rhsStr = m.groups()
                    op = (op_prefix or "") + "="
                    self._handle_python_assignment(var, op, rhsStr)
                else:
                    if log_fn: log_fn(f"Unknown command: {line}")
            else:
                if log_fn: log_fn(f"Unknown command: {line}")
            i += 1
        return i

    def _execute_function(self, func_name: str, arg_vals: list[float], log_fn=None) -> float:
        arg_names, bstart, bend = self._functions[func_name]
        
        # pad args if needed
        while len(arg_vals) < len(arg_names):
            arg_vals.append(0.0)
            
        saved_vars = self._variables.copy()
        for arg_name, arg_val in zip(arg_names, arg_vals):
            self._variables[arg_name] = arg_val
            
        result_val = 0.0
        try:
            self._exec_block(self._script_lines, bstart, bend, log_fn)
        except ReturnFunc as ret_exc:
            result_val = ret_exc.value

        self._variables = saved_vars
        self._variables["_return_"] = result_val
        return result_val

    def _handle_set(self, tokens: list[str]):
        var = tokens[1]
        if len(tokens) == 2:
            self._variables[var] = 0.0
            return
        if len(tokens) == 4 and tokens[2] in ("+", "-", "*", "/", "%", "**"):
            op = tokens[2]
            val = self._resolve_value(tokens[3])
            cur = self._variables.get(var, 0)
            if op == "+": self._variables[var] = cur + val
            elif op == "-": self._variables[var] = cur - val
            elif op == "*": self._variables[var] = cur * val
            elif op == "/": self._variables[var] = cur / val if val != 0 else cur
            elif op == "%": self._variables[var] = cur % val if val != 0 else cur
            elif op == "**": self._variables[var] = cur ** val
            return
        expr = " ".join(tokens[2:])
        try:
            val = self._eval_expr(expr)
            self._variables[var] = float(val)
        except Exception:
            self._variables[var] = 0.0

    def _handle_python_assignment(self, var: str, op: str, rhsStr: str):
        if not rhsStr:
            val = 0.0
        else:
            try:
                val = float(self._eval_expr(rhsStr))
            except Exception:
                val = 0.0
            
        if op == "=":
            self._variables[var] = val
            return

        cur = self._variables.get(var, 0)
        try:
            if op == "+=": self._variables[var] = cur + val
            elif op == "-=": self._variables[var] = cur - val
            elif op == "*=": self._variables[var] = cur * val
            elif op == "/=": self._variables[var] = cur / val if val != 0 else cur
            elif op == "%=": self._variables[var] = cur % val if val != 0 else cur
            elif op == "**=": self._variables[var] = cur ** val
        except Exception:
            self._variables[var] = val

    def _handle_if(self, lines: list[str], start: int, block_end: int, log_fn) -> int:
        branches: list[tuple[str, int, int]] = []
        i = start
        depth = 0
        branch_starts: list[int] = [start]

        for j in range(start, block_end):
            toks = _tokenize(lines[j])
            if not toks: continue
            tok0 = toks[0].lower()
            if tok0 in ("loop", "if", "do"):
                if j != start:
                    depth += 1
            elif tok0 in ("end", "until", "}"):
                if len(toks) > 1 and toks[1].lower() in ("else", "elif") and depth == 0:
                    branch_starts.append(j)
                elif depth == 0 and tok0 in ("end", "}"):
                    branch_starts.append(j)
                    break
                elif depth > 0:
                    depth -= 1
            elif tok0 in ("elif", "else") and depth == 0:
                branch_starts.append(j)

        for idx in range(len(branch_starts) - 1):
            cond_line = lines[branch_starts[idx]]
            body_start = branch_starts[idx] + 1
            body_end = branch_starts[idx + 1]
            branches.append((cond_line, body_start, body_end))

        end_idx = branch_starts[-1]

        for cond_line, bstart, bend in branches:
            toks = _tokenize(cond_line)
            if not toks: continue
            cmd = toks[0].lower()

            m = re.match(r'^(if|elif|})\s+(.*?)\s*\{?$', cond_line.strip(), re.IGNORECASE)
            
            expr_str = ""
            if m:
                # If cmd is } and the next is elif, it looks like `} elif x == 1 {`
                if cmd == "}" and len(toks) > 1 and toks[1].lower() == "elif":
                    m_elif = re.match(r'^.*?\belif\s+(.*?)\s*\{?$', cond_line.strip(), re.IGNORECASE)
                    if m_elif:
                        expr_str = m_elif.group(1).strip()
                else:
                    expr_str = m.group(2).strip()
            
            if cmd == "else":
                self._exec_block(lines, bstart, bend, log_fn)
                break
            if cmd == "}":
                if len(toks) > 1 and toks[1].lower() == "else":
                    self._exec_block(lines, bstart, bend, log_fn)
                    break
                elif len(toks) > 1 and toks[1].lower() == "elif":
                    if self._eval_condition(toks[2:], expr_str):
                        self._exec_block(lines, bstart, bend, log_fn)
                        break
                # Only if/elif is matched, a bare } doesn't trigger anything.
                # However logic already breaks and bypasses this normally.
            else:
                if self._eval_condition(toks[1:], expr_str):
                    self._exec_block(lines, bstart, bend, log_fn)
                    break
                    
        return end_idx + 1

    def _eval_condition(self, tokens: list[str], raw_expr: str = "") -> bool:
        if raw_expr:
            try:
                return bool(self._eval_expr(raw_expr))
            except Exception:
                pass
                
        if tokens:
            expr = " ".join(tokens)
            try:
                # If evaluating the whole expr throws, we fallback
                # but eval returns a float/bool
                # Unfortunately python's eval may fail on syntax error
                return bool(self._eval_expr(expr))
            except Exception:
                pass
        if not tokens:
            return False
        if tokens[0].lower() == "not":
            return not self._eval_condition(tokens[1:])
        if "or" in tokens:
            idx = tokens.index("or")
            return self._eval_condition(tokens[:idx]) or self._eval_condition(tokens[idx+1:])
        if "and" in tokens:
            idx = tokens.index("and")
            return self._eval_condition(tokens[:idx]) and self._eval_condition(tokens[idx+1:])
            
        if len(tokens) == 1:
            return bool(self._variables.get(tokens[0], 0))

        cmd = tokens[0].lower()
        if cmd == "exists":
            images, thresh = self._parse_find_args(tokens[1:])
            for img in images:
                if self._find_template(img, thresh) is not None:
                    return True
            return False
        if cmd == "exists_exact":
            images, thresh = self._parse_find_args(tokens[1:])
            for img in images:
                if self._find_template_exact(img, thresh) is not None:
                    return True
            return False

        if len(tokens) >= 3:
            var_val = self._variables.get(tokens[0], 0)
            op = tokens[1]
            rhs_tok = tokens[2]
            if rhs_tok.lower() in ("true", "false"):
                rhs = 1.0 if rhs_tok.lower() == "true" else 0.0
            else:
                try:
                    rhs = float(rhs_tok)
                except ValueError:
                    rhs = self._variables.get(rhs_tok, 0)
            if op == ">": return var_val > rhs
            elif op == "<": return var_val < rhs
            elif op in ("==", "="): return var_val == rhs
            elif op == ">=": return var_val >= rhs
            elif op == "<=": return var_val <= rhs
            elif op == "!=": return var_val != rhs
        return False

    def _parse_find_args(self, tokens: list[str]) -> tuple[list[str], float]:
        images = []
        threshold = 0.8
        for t in tokens:
            if (t.startswith("'") and t.endswith("'")) or \
               (t.startswith('"') and t.endswith('"')):
                images.append(t[1:-1])
            elif t.endswith(".png") or t.endswith(".jpg"):
                images.append(t)
            else:
                try:
                    threshold = float(self._resolve_value(t))
                except Exception:
                    pass
        return images, threshold

    def _parse_wait_args(self, tokens: list[str]) -> tuple[list[str], float]:
        images = []
        timeout = 0.0
        for t in tokens:
            if (t.startswith("'") and t.endswith("'")) or \
               (t.startswith('"') and t.endswith('"')):
                images.append(t[1:-1])
            elif t.endswith(".png") or t.endswith(".jpg"):
                images.append(t)
            else:
                try:
                    timeout = float(self._resolve_value(t))
                except Exception:
                    pass
        return images, timeout

    def _wait_for_images(self, image_names: list[str], timeout: float, log_fn) -> Optional[tuple[str, tuple[int, int]]]:
        start = time.time()
        names_str = ", ".join(image_names)
        if timeout > 0:
            if log_fn: log_fn(f"Waiting for [{names_str}] (timeout {timeout}s)...")
        else:
            if log_fn: log_fn(f"Waiting for [{names_str}] (no timeout)...")
        while True:
            if self._stop_event.is_set():
                return None
            if timeout > 0 and time.time() - start >= timeout:
                if log_fn: log_fn(f"Timeout waiting for [{names_str}]")
                return None
            for img in image_names:
                pos = self._find_template(img)
                if pos:
                    if log_fn: log_fn(f"Found {img} at {pos}")
                    return (img, pos)
            time.sleep(0.5)

    def _wait_for_image(self, image_name: str, timeout: float, log_fn) -> Optional[tuple[int, int]]:
        result = self._wait_for_images([image_name], timeout, log_fn)
        if result:
            return result[1]
        return None

    def _interruptible_sleep(self, seconds: float):
        end_time = time.time() + seconds
        while time.time() < end_time:
            if self._stop_event.is_set():
                return
            time.sleep(min(0.1, end_time - time.time()))

    def _eval_expr(self, expr: str):
        local_ns = {k: v for k, v in self._variables.items()}
        def exists(*args):
            images = []
            thresh = 0.8
            for arg in args:
                if isinstance(arg, (int, float)): thresh = float(arg)
                elif isinstance(arg, str): images.append(arg)
            for img in images:
                if self._find_template(img, thresh) is not None: return True
            return False
            
        def exists_exact(*args):
            images = []
            thresh = 0.8
            for arg in args:
                if isinstance(arg, (int, float)): thresh = float(arg)
                elif isinstance(arg, str): images.append(arg)
            for img in images:
                if self._find_template_exact(img, thresh) is not None: return True
            return False
        import math
        local_ns.update({
            "exists": exists,
            "exists_exact": exists_exact,
            "rand": random.random,
            "randint": random.randint,
            "min": min,
            "max": max,
            "abs": abs,
            "math": math,
        })
        
        # Inject custom DSL functions
        def build_dsl_func(fname):
            return lambda *args: self._execute_function(fname, list(args))
            
        for fname in self._functions:
            local_ns[fname] = build_dsl_func(fname)
            
        return eval(expr, {"__builtins__": {}}, local_ns)

    def _resolve_value(self, token: str) -> float:
        if (token.startswith("'") and token.endswith("'")) or (
            token.startswith('"') and token.endswith('"')
        ):
            token = token[1:-1]
        try:
            return float(token)
        except ValueError:
            val = self._eval_expr(token)
            try:
                return float(val)
            except Exception:
                return self._variables.get(token, 0)
