from doctr.io import DocumentFile
from doctr.models import ocr_predictor
import json


model = ocr_predictor(pretrained=True)
# PDF
doc = DocumentFile.from_images(r"C:\Users\arint\Downloads\ocrtest.jpg")
# Analyze
result = model(doc)

output = result.export()


with open(r"C:\Users\arint\Downloads\example_1.json", "w") as f:
    f.write(json.dumps(output, indent=1))
f.close()

with open(r"C:\Users\arint\Downloads\example_1.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Extraire tous les mots
words = []
for page in data.get("pages", []):
    for block in page.get("blocks", []):
        for line in block.get("lines", []):
            for word in line.get("words", []):
                value = word.get("value")
                if value:
                    words.append(value)

# Concaténer les mots en une seule chaîne
result = " ".join(words)
print(result)