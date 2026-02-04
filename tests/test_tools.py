# tests/test_tools.py
"""
Give these instructions to Copilot. Keep tests deterministic and file-system safe.

Goal:
- Test that tools.py correctly creates/loads/appends JSON list files.
- Do NOT call Ollama / any LLM in tests.
- Use pytest + tmp_path fixture.

Write tests for:
1) test_load_json_list_creates_file_if_missing
   - create a path under tmp_path that doesn't exist
   - call load_json_list(path)
   - assert file now exists
   - assert returned value is []

2) test_add_artifact_appends
   - create empty artifacts file under tmp_path
   - call add_artifact(artifacts_path, {"id":"A1","language":"branch_a","type":"inscription","text":"foo","metadata":{}})
   - call load_artifacts and assert len == 1 and id == "A1"

3) test_append_research_log_appends
   - same as above but using append_research_log
   - assert len == 1 and entry id matches

4) test_search_artifacts_finds_matches
   - create in-memory list of artifacts:
     [{"id":"A1","language":"branch_a","type":"inscription","text":"kar mel","metadata":{}},
      {"id":"A2","language":"branch_b","type":"inscription","text":"haru mer","metadata":{}}]
   - call search_artifacts(artifacts, "kar") -> returns first only
   - call search_artifacts(artifacts, "branch_b") -> returns second only

5) test_invalid_json_raises
   - write invalid JSON to a tmp file (e.g. "{not json")
   - calling load_json_list should raise RuntimeError

Implementation notes:
- import from ghostroot.tools
- avoid hardcoded repo paths; always use tmp_path
- keep asserts simple and explicit
"""
