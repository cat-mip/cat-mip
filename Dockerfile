FROM squidfunk/mkdocs-material

# Install plugins
RUN pip install --no-cache-dir \
    mkdocs-awesome-pages-plugin \
    mkdocs-git-revision-date-localized-plugin \
    pyyaml

# Copy repo (including scripts)
# COPY . /docs

# WORKDIR /docs

# Generate MD files + serve
# CMD sh -c "python scripts/generate_md.py && mkdocs serve --dev-addr 0.0.0.0:8000"
