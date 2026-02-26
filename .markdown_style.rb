all
# Match your project-wide 100-char limit
rule 'MD013', :line_length => 100
# Match your 2-space indent standard
rule 'MD007', :indent => 2
# Allow HTML (common for alignment in hardware docs)
exclude_rule 'MD033'
