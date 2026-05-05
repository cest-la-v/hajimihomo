.PHONY: help build build-groups build-dry validate extract extract-check dev web-build web-dev web-install vendor-sync vendor-coverage

GROUPS ?= proxy/telegram,block/ads,direct/cn
JOBS   ?= 8

help:
	@echo "Ruleset builder:"
	@echo "  make build           build everything (atomics + groups)"
	@echo "  make build-groups    build catalog groups only"
	@echo "  make build-groups GROUPS=proxy/telegram,block/ads"
	@echo "  make build-dry       dry-run: validate build graph, no output"
	@echo "  make validate        validate source YAML files"
	@echo "  make extract         re-extract sources from bm7 vendor (updates categories.yaml)"
	@echo "  make extract-check   check coverage gaps vs bm7 without writing"
	@echo ""
	@echo "Vendor management:"
	@echo "  make vendor-sync     clone/update all repos referenced by repo: sources"
	@echo "  make vendor-coverage generate vendor coverage report (scripts/validate/coverage-report.md)"
	@echo ""
	@echo "Profile builder (web):"
	@echo "  make web-install     install web dependencies (js-yaml)"
	@echo "  make web-build       build static site to web/dist/"
	@echo "  make dev             dev server (CDN rulesets)"
	@echo "  make dev-local       dev server using local dist/ rulesets"

build:
	python3 scripts/build.py --with-groups --jobs $(JOBS)

build-groups:
	python3 scripts/build.py --all-groups --jobs $(JOBS)

build-groups-only:
	python3 scripts/build.py --groups $(GROUPS) --jobs $(JOBS)

build-dry:
	python3 scripts/build.py --all-groups --dry-run

validate:
	python3 scripts/validate.py

extract:
	python3 scripts/extract_sources.py

extract-check:
	python3 scripts/extract_sources.py --check

vendor-sync:
	python3 scripts/vendor_sync.py --jobs $(JOBS)

vendor-coverage:
	python3 scripts/validate/coverage.py --output scripts/validate/coverage-report.md

vendor-analysis:
	python3 scripts/analyze/vendor_analysis.py --jobs $(JOBS)

web-install:
	cd web && bun install

web-build: web-install
	cd web && bun run build.ts

dev: web-install
	cd web && bun run dev.ts

dev-local: web-install
	cd web && RULESET_DIR=../dist bun run dev.ts
