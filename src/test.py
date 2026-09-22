import pandas as pd
df = pd.read_csv("../data/ATSMS26.csv")
print([repr(x) for x in df["CENTRO DE TRANSFERENCIA"].unique()])