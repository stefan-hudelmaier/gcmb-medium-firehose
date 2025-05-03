postgres-port-forward:
  {{justfile_directory()}}/scripts/postgres-port-forward.sh

tests:
  .venv/bin/python -m unittest test_atom_entry_serializer.py -v
