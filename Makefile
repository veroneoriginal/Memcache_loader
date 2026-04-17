.PHONY: up down dry run reset test

go:
	python -m source.memc_load --dry --pattern="data/*.tsv.gz"

# Поднять memcache-кластер (4 инстанса)
up:
	docker compose up -d

# Остановить и удалить контейнеры
down:
	docker compose down

# Запуск без записи в memcache (dry-run)
dry:
	python -m source.memc_load --dry --pattern="data/*.tsv.gz"

# Запуск с реальной записью в memcache
run:
	python -m source.memc_load --pattern="data/*.tsv.gz"

# Восстановить обработанные файлы для повторного запуска
reset:
	@cd data && for f in .*.tsv.gz; do [ -f "$$f" ] && mv "$$f" "$${f#.}"; done; true
	@echo "Files in data/ restored"

# Запуск тестов
test:
	python -m pytest source/test.py -v

# Проверка PEP8
lint:
	flake8 source/ --exclude=appsinstalled_pb2.py
