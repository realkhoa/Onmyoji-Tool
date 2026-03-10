import threading

class DSLError(Exception):
    pass

class BreakLoop(Exception):
    pass

class ContinueLoop(Exception):
    pass

class ReturnFunc(Exception):
    def __init__(self, value: float = 0.0):
        self.value = value
