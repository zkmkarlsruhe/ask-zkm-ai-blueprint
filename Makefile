# Convenience targets for the museum-ai-stack blueprint.
#
# Each component has its own docker-compose.yml; this Makefile just
# delegates so you don't have to remember the cd-and-up dance.

STACKS := gateway webui cost-tracker
PROXIES := proxies/oauth-translator proxies/local-bridge proxies/document-preprocessor
MCPS := mcps/hello-world mcps/opac

.PHONY: help networks up down logs ps lint check-env

help:
	@echo "Targets:"
	@echo "  make networks        Create the shared 'proxy' and 'ai-bus' docker networks"
	@echo "  make up              docker compose up -d for the three core stacks"
	@echo "  make down            docker compose down for the three core stacks"
	@echo "  make logs            tail logs from all running stacks"
	@echo "  make ps              show containers across all stacks"
	@echo "  make lint            ruff check on every Python source dir"
	@echo "  make check-env       fail loudly if any required .env is missing"
	@echo ""
	@echo "Stacks: $(STACKS)"
	@echo "MCPs:   $(MCPS)"
	@echo "Proxies (optional): $(PROXIES)"

networks:
	@docker network create proxy 2>/dev/null || true
	@docker network create ai-bus 2>/dev/null || true
	@echo "ok: proxy + ai-bus networks ready"

up: networks check-env
	@for s in $(STACKS); do \
		echo "==> $$s up"; \
		(cd $$s && docker compose up -d) || exit 1; \
	done

down:
	@for s in $(STACKS); do \
		echo "==> $$s down"; \
		(cd $$s && docker compose down) || true; \
	done

logs:
	@for s in $(STACKS); do \
		echo "==> $$s"; \
		(cd $$s && docker compose logs --tail=20 --no-color) || true; \
	done

ps:
	@for s in $(STACKS) $(MCPS) $(PROXIES); do \
		echo "==> $$s"; \
		(cd $$s && docker compose ps) || true; \
	done

check-env:
	@for s in $(STACKS); do \
		if [ ! -f $$s/.env ]; then \
			echo "missing: $$s/.env  (copy from $$s/.env.example)"; exit 1; \
		fi; \
	done
	@echo "ok: all required .env files present"

lint:
	@command -v ruff >/dev/null || { echo "install ruff: pip install ruff"; exit 1; }
	ruff check cost-tracker/app mcps/hello-world/src mcps/opac/src \
	           proxies/oauth-translator/src proxies/local-bridge/src \
	           proxies/document-preprocessor/src gateway/hooks
