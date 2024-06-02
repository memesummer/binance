my_dict = {'key1': [[1, 2], [2, 3]]}

result = '；'.join(f"{key}:{','.join(map(str, values))}" for key, values in my_dict.items())

print(result)
