# Clinic FAQ content maintenance

The FAQ agent reads `data/clinic_faq.json`. Each entry is an approved, patient-facing fact:

```json
[
  {
    "id": "clinic-hours",
    "question": "What are the clinic opening hours?",
    "keywords": ["hours", "opening", "open"],
    "answer": "<clinic-approved answer>",
    "source": {
      "title": "<approved source document or reviewer>",
      "reviewed_at": "YYYY-MM-DD",
      "owner": "<clinic content owner>"
    }
  }
]
```

Required fields are `question` and `answer`. `id`, `keywords`, and `source` metadata are optional but recommended; when `id` is present, the FAQ response includes it as a source reference.

## Update procedure
1. Obtain the answer from an authorized clinic operator or an official clinic document.
2. Confirm the answer is current, patient-facing, and does not include private patient information or unsupported medical advice.
3. Add or update an entry in `data/clinic_faq.json`; use concise question variants/keywords and an exact approved answer.
4. Validate JSON syntax and run `python -m pytest tests/test_knowledge_base.py tests/test_faq.py -q -p no:cacheprovider` plus the full suite.
5. Have the clinic content owner review the change before release. Record the reviewer and review date in the project’s normal change record.

Do not infer hours, location, prices, insurance, services, or policies from appointment-slot CSV data. If no approved answer exists, leave the FAQ store empty for that topic; the agent is designed to escalate unresolved FAQ questions to the local human-support queue with a truthful pending status.
