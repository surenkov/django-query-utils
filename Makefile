.PHONY: install
install:
	python3 -m venv .env
	. .env/bin/activate
	python3 -m pip install build twine
	python3 -m pip install -e .[dev,postgres]


.PHONY: activate
activate:
	. .env/bin/activate


.PHONY: dist
dist: activate
dist:
	python3 -m build


.PHONY: build
test: A=
build:
	docker compose build $(A)


.PHONY: test
test: A=
test:
	docker compose run --rm tests pytest $(A)


.PHONY: upload
upload: activate
upload:
	python3 -m twine upload dist/*


.PHONY: upload-test
upload-test: activate
upload-test:
	python3 -m twine upload --repository testpypi dist/*


.PHONY: clean
clean:
	rm -rf dist/* .env/ *.egg-info/
	docker compose down -v
