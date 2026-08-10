VENV := .venv
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
FACTORY := $(VENV)/bin/agent-factory
STAMP := $(VENV)/.stamp

.DEFAULT_GOAL := help
.PHONY: help venv list validate build install install-link uninstall-dry test clean distclean

help:
	@echo "make venv          create .venv and install the factory (editable)"
	@echo "make list          list every agent in agents/"
	@echo "make validate      check all agents against the canonical schema"
	@echo "make build         render agents into dist/<target>/"
	@echo "make install       build, then copy into the runtime's user config"
	@echo "make install-link  same, but symlink so edits apply after a rebuild"
	@echo "make test          run the test suite"
	@echo "make clean         remove dist/"
	@echo "make distclean     remove dist/ and .venv/"

venv: $(STAMP)

$(STAMP): pyproject.toml requirements.txt
	python3 -m venv $(VENV)
	$(PIP) install -q --upgrade pip
	$(PIP) install -q -r requirements.txt
	@touch $(STAMP)

list: venv
	@$(FACTORY) list

validate: venv
	@$(FACTORY) validate

build: venv
	@$(FACTORY) build

install: venv
	@$(FACTORY) install --scope user

install-link: venv
	@$(FACTORY) install --scope user --link

uninstall-dry: venv
	@$(FACTORY) install --scope user --dry-run

test: venv
	@$(PYTEST)

clean:
	rm -rf dist

distclean: clean
	rm -rf $(VENV) .pytest_cache src/*.egg-info
