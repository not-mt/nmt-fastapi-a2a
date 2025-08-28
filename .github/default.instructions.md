---
applyTo: "**/*.py"
---

Update docstrings using these guidelines:
- Use PEP 257 (Google style)
- Ensure all functions, methods, classes, and modules have clear and concise docstrings.
- All non-tests should have PEP 484 compliant type hints.
- Do not include types in docstrings; type hints will be used to specify parameter/attribute types.
- All docstrings should be complete sentences ending with a period.
- All docstrings should start with '"""' alone on the beginning and end line, with the content of the docstring between the '"""'.
- No blank lines are allowed after function docstrings.
- Use triple double quotes for docstrings.
- `__init__` methods should not have a docstring; instead, combine it with the docstring of the class.
- Docstrings should be concise yet descriptive, providing enough context for understanding the purpose and usage of the code element.
