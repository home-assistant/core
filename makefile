commit:
	git add .
	git restore --staged makefile
	git commit -m "$(msg)"