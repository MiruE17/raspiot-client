import random

def get_random_in_range(min_val, max_val, decimals):
    return round(random.uniform(min_val, max_val), decimals)

value1 = get_random_in_range(20, 40, 1)
value2 = get_random_in_range(0, 1, 1)
value3 = get_random_in_range(20, 40, 1)
value4 = get_random_in_range(0, 1, 1)

values_array = [value1, value2, value3, value4]
values_string = ','.join(str(v) for v in values_array)

print(values_string)