from transformers import AutoModelForCausalLM, AutoTokenizer

model_name = "bigcode/starcoder"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name)

code = """
def greet(name):
    return f"Hello, {name}!"
"""

inputs = tokenizer(code, return_tensors="pt")
outputs = model.generate(**inputs, max_new_tokens=100)
explanation = tokenizer.decode(outputs[0], skip_special_tokens=True)

print(explanation)


