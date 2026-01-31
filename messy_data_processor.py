"""
Data processor with poor code quality
"""


def process(data):
    # Bug: Too complex, needs refactoring
    if data:
        if len(data) > 0:
            if isinstance(data, list):
                if data[0]:
                    if 'name' in data[0]:
                        if data[0]['name']:
                            if len(data[0]['name']) > 0:
                                return data[0]['name'].upper()
    return None


def transform_data(items):
    # Bug: Modifying list while iterating
    for item in items:
        if item % 2 == 0:
            items.remove(item)
    return items


# Bug: Comparison with None using ==
def check_value(val):
    if val == None:
        return False
    return True


# Bug: Using mutable default argument
def append_to_list(item, lst=[]):
    lst.append(item)
    return lst


class DataProcessor:
    # Bug: No docstring
    def __init__(self):
        self.data = None
        
    # Bug: Method does too many things
    def process_and_save_and_validate(self, input_data, filename, validation_rules):
        # Bug: Not using validation_rules parameter
        self.data = input_data
        
        # Bug: Nested try-except blocks
        try:
            try:
                processed = self.process(input_data)
                self.save(processed, filename)
            except Exception as e:
                print(e)  # Bug: Using print instead of logging
        except:
            pass
    
    def process(self, data):
        # Bug: Creating unnecessary lists
        result = []
        for item in data:
            result.append(item * 2)
        return result  # Should use list comprehension
    
    def save(self, data, filename):
        # Bug: File not properly closed in case of exception
        f = open(filename, 'w')
        f.write(str(data))
        f.close()


# Bug: Magic numbers everywhere
def calculate_score(value):
    if value > 100:
        return value * 1.5 + 42 - 17
    elif value > 50:
        return value * 0.75 + 23
    else:
        return value * 0.5 + 11


# Bug: Variable shadowing builtin
def process_list(list):
    sum = 0
    for item in list:
        sum += item
    return sum / len(list)


# Bug: Duplicate code
def format_name_first(name):
    return name.strip().title().replace("  ", " ")

def format_name_second(name):
    return name.strip().title().replace("  ", " ")
