"""
A calculator module with intentional bugs for testing
"""

import os
import sys


def add(a, b):
    # Bug: No type checking
    return a + b


def divide(x, y):
    # Bug: No zero division handling
    result = x / y
    return result


def calculate_average(numbers):
    # Bug: Empty list not handled
    total = 0
    for i in range(len(numbers)):  # Bug: Using range(len()) instead of enumerate
        total += numbers[i]
    
    return total / len(numbers)


class Calculator:
    def __init__(self):
        self.history = []
        self.result = 0
    
    def add_to_history(self, operation, result):
        # Bug: Unbounded list growth - memory leak
        self.history.append({"op": operation, "result": result})
    
    def get_result(self):
        # Bug: Mutable default argument in wrong place, but also...
        return self.result
    
    def calculate(self, numbers=[]):  # Bug: Mutable default argument
        # Bug: SQL injection vulnerability simulation
        query = "SELECT * FROM results WHERE id = " + str(numbers[0])
        
        # Bug: Accessing index without checking if list is empty
        first = numbers[0]
        
        # Bug: Using eval - security risk
        result = eval(str(first) + " + 10")
        
        return result


def process_data(data):
    # Bug: Catching generic exception
    try:
        result = data['key']
    except:  # Bug: Bare except
        pass  # Bug: Silent failure
    
    # Bug: Variable might not be defined
    return result


# Bug: Global variable that gets mutated
GLOBAL_COUNTER = 0

def increment_counter():
    # Bug: Missing global keyword
    GLOBAL_COUNTER += 1
    return GLOBAL_COUNTER


# Bug: Unused function
def unused_function():
    print("This is never called")
    x = 10
    y = 20
    # Bug: Dead code
    z = x + y
    return None


# Bug: Function with too many arguments
def complex_function(a, b, c, d, e, f, g, h, i, j):
    return a + b + c + d + e + f + g + h + i + j


# Bug: Inconsistent naming
def CalculateSomething(value):  # Bug: PascalCase for function
    MyVariable = value * 2  # Bug: PascalCase for variable
    return MyVariable


if __name__ == "__main__":
    # Bug: No error handling
    calc = Calculator()
    print(divide(10, 0))  # Will crash
    print(calculate_average([]))  # Will crash
