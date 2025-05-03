postgres-port-forward:
  {{justfile_directory()}}/scripts/postgres-port-forward.sh

tests:
  .venv/bin/python -m unittest test_atom_entry_serializer.py -v

run:
  uv run python main.py

send-example-update:
  curl -X POST -d @example-medium-update.xml http://127.0.0.1:8080/websub/webhook -H 'link: <https://medium.com/feed/tag/technology\>; rel="self";'
