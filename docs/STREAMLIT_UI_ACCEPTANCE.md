# Streamlit UI acceptance checklist

Run the API and UI in separate terminals. Configure `API_URL` to match the API address. When API authentication is enabled, configure the same `API_ACCESS_TOKEN` in both API and UI processes.

## Manual acceptance

- [ ] The Patient ID field is masked and rejects non-numeric IDs and values outside 1000000–99999999 without making an API request.
- [ ] A valid synthetic test ID can send a message; the transcript shows user and assistant turns.
- [ ] The interface displays a loading state while waiting for the API.
- [ ] Invalid API requests, 401/403, 503, timeouts, and connection errors show understandable messages without stack traces or secret values.
- [ ] A new conversation creates a different session ID and clears the visible transcript.
- [ ] A pending human-support response displays the case ID and states that human review is pending; it does not imply a human has already answered.
- [ ] User and assistant text is rendered without enabling raw HTML.
- [ ] Layout remains usable in a narrow browser window and keyboard navigation reaches the input and controls.

## Automated checks

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_ui_helpers.py tests\test_api.py -q -p no:cacheprovider
```

Automated Streamlit AppTest coverage is available in `tests/test_streamlit_ui.py` for invalid IDs, successful response rendering, pending escalation feedback, and starting a new conversation. Manual browser validation is still required for responsive layout, keyboard navigation, and a live API run before release.
