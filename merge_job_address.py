import pandas as pd
import os
import time

# Paths
processed_path = os.path.join('data', 'processed', 'COMBINED_DATA_PROCESSED1.csv')
raw_path = os.path.join('data', 'raw', 'job', 'combined_data.csv')

# Backup processed file
timestamp = time.strftime('%Y%m%d_%H%M%S')
backup_path = processed_path + f'.backup_{timestamp}'
if os.path.exists(processed_path):
    print(f'Creating backup: {backup_path}')
    os.replace(processed_path, backup_path)

# Read small chunks to infer columns
print('Reading processed CSV (head)...')
proc_head = pd.read_csv(backup_path if os.path.exists(backup_path) else processed_path, nrows=5, dtype=str, encoding='utf-8', engine='python')
print('Reading raw CSV (head)...')
raw_head = pd.read_csv(raw_path, nrows=5, dtype=str, encoding='utf-8', engine='python')

# Heuristics to find job id and address columns
def find_column(cols, candidates):
    for c in candidates:
        if c in cols:
            return c
    # try case-insensitive
    lower_map = {col.lower(): col for col in cols}
    for c in candidates:
        if c.lower() in lower_map:
            return lower_map[c.lower()]
    return None

proc_cols = proc_head.columns.tolist()
raw_cols = raw_head.columns.tolist()

job_id_candidates = ['job_id', 'jobid', 'id', 'jobID', 'jobId']
address_candidates = ['job_address', 'job_address_clean', 'address', 'job_location', 'location']

proc_job_col = find_column(proc_cols, job_id_candidates)
raw_job_col = find_column(raw_cols, job_id_candidates)
raw_address_col = find_column(raw_cols, address_candidates)

if proc_job_col is None:
    raise SystemExit('Could not find job id column in processed CSV. Columns: ' + ','.join(proc_cols))
if raw_job_col is None:
    raise SystemExit('Could not find job id column in raw CSV. Columns: ' + ','.join(raw_cols))
if raw_address_col is None:
    raise SystemExit('Could not find address column in raw CSV. Columns: ' + ','.join(raw_cols))

print('Detected columns:')
print('Processed job id column:', proc_job_col)
print('Raw job id column:', raw_job_col)
print('Raw address column:', raw_address_col)

# Read full data (use dtype=str to avoid dtype issues)
print('Reading full CSVs...')
proc_df = pd.read_csv(backup_path if os.path.exists(backup_path) else processed_path, dtype=str, encoding='utf-8', engine='python')
raw_df = pd.read_csv(raw_path, dtype=str, encoding='utf-8', engine='python')

# Merge
print('Merging address into processed dataframe...')

# Debug: show columns to help diagnose KeyError
print('Processed columns:', proc_df.columns.tolist())
print('Raw columns:', raw_df.columns.tolist())

merged = proc_df.merge(raw_df[[raw_job_col, raw_address_col]].drop_duplicates(raw_job_col), how='left', left_on=proc_job_col, right_on=raw_job_col)

# Create or replace column `job_detail_address` from raw_address_col
try:
    merged['job_detail_address'] = merged[raw_address_col]
except KeyError:
    print(f"Column '{raw_address_col}' not found in merged dataframe. Attempting fallback mapping.")
    # Build mapping from raw job id -> address and map onto processed dataframe
    mapping = raw_df[[raw_job_col, raw_address_col]].drop_duplicates(raw_job_col).set_index(raw_job_col)[raw_address_col].to_dict()
    merged['job_detail_address'] = merged[proc_job_col].map(mapping)
    # If still all NaN, try to find any address-like column in merged
    if merged['job_detail_address'].isna().all():
        addr_cols = [c for c in merged.columns if 'address' in c.lower()]
        if addr_cols:
            print('Found address-like columns in merged:', addr_cols)
            merged['job_detail_address'] = merged[addr_cols[0]]
        else:
            print('No address-like fallback column found; `job_detail_address` will be NaN where unmapped.')

# Drop the extra raw job id column if it was added and names differ
if raw_job_col != proc_job_col and raw_job_col in merged.columns:
    merged = merged.drop(columns=[raw_job_col])

# Save back to processed_path
print('Saving merged CSV to', processed_path)
merged.to_csv(processed_path, index=False, encoding='utf-8')
print('Done.')
