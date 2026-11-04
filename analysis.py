"""Quy trình dùng chung cho notebook, báo cáo và Dashboard."""
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parent
ASSETS = ['residential_assets_value', 'commercial_assets_value',
          'luxury_assets_value', 'bank_asset_value']
FIELDS = ['loan_id', 'no_of_dependents', 'education', 'self_employed',
          'income_annum', 'loan_amount', 'loan_term', 'cibil_score', *ASSETS,
          'loan_status']
BANDS = ['300–549', '550–649', '650–749', '750–900']

def prepare(raw):
    """Giữ nguyên dòng, đánh dấu tài sản âm, không tự điền số liệu."""
    df = raw.copy()
    df.columns = df.columns.str.strip()
    missing = set(FIELDS) - set(df.columns)
    if missing:
        raise ValueError(f'Thiếu cột: {sorted(missing)}')
    for col in df.select_dtypes('object'):
        df[col] = df[col].str.strip()
    for col in set(FIELDS) - {'education', 'self_employed', 'loan_status'}:
        df[col] = pd.to_numeric(df[col], errors='raise')
    if df[FIELDS].isna().any().any():
        raise ValueError('Nguồn có giá trị thiếu. Cần kiểm tra trước khi sử dụng.')
    if df.loan_id.duplicated().any():
        raise ValueError('Trùng mã hồ sơ, cần đối chiếu nguồn.')
    if not df.loan_status.isin(['Approved', 'Rejected']).all():
        raise ValueError('Trạng thái phê duyệt không hợp lệ.')
    if not df.education.isin(['Graduate', 'Not Graduate']).all():
        raise ValueError('Giá trị học vấn không hợp lệ.')
    if not df.self_employed.isin(['Yes', 'No']).all():
        raise ValueError('Giá trị tự kinh doanh không hợp lệ.')
    if ((df[['income_annum', 'loan_amount', 'loan_term']] <= 0).any().any()
        or (~df.cibil_score.between(300, 900)).any()
        or (df.no_of_dependents < 0).any()):
        raise ValueError('Có thu nhập/khoản vay/kỳ hạn/CIBIL/số người phụ thuộc bất hợp lệ.')
    df['asset_issue'] = df[ASSETS].lt(0).any(axis=1)
    df['residential_assets_value_raw'] = df.residential_assets_value
    df[ASSETS] = df[ASSETS].mask(df[ASSETS].lt(0))
    # Chỉ cộng khi đủ bốn thành phần, tránh tổng tài sản thiếu bị coi là đầy đủ.
    df['total_assets'] = df[ASSETS].sum(axis=1, min_count=4)
    df['approved'] = df.loan_status.eq('Approved').astype(int)
    df['status_vi'] = df.loan_status.map({'Approved': 'Được duyệt', 'Rejected': 'Từ chối'})
    df['cibil_band'] = pd.cut(df.cibil_score, [299, 549, 649, 749, 900], labels=BANDS)
    # Khoản vay / thu nhập năm là số lần, KHÔNG phải hệ số trả nợ DTI.
    df['loan_income_ratio'] = df.loan_amount / df.income_annum
    df['income_group'] = pd.qcut(df.income_annum, 4, labels=['Q1', 'Q2', 'Q3', 'Q4'])
    return df

def load_data(path=None):
    return prepare(pd.read_csv(path or ROOT / 'data/loan_approval_dataset.csv'))

def kpis(df):
    n = len(df)
    return {'total': n, 'approved': int(df.approved.sum()),
            'rejected': int(n - df.approved.sum()),
            'approval_rate': float(df.approved.mean()) if n else None,
            'requested_amount': float(df.loan_amount.sum()),
            'mean_cibil': float(df.cibil_score.mean()) if n else None,
            'asset_issues': int(df.asset_issue.sum())}

def grouped(df, col):
    out = df.groupby(col, observed=True).agg(
        total=('loan_id', 'size'), approved=('approved', 'sum'))
    out['rate'] = out.approved / out.total * 100
    out['rejected'] = out.total - out.approved
    return out.reset_index()

def filter_data(df, status, education, employed, score, term, income):
    return df.loc[df.loan_status.isin(status) & df.education.isin(education)
        & df.self_employed.isin(employed) & df.cibil_score.between(*score)
        & df.loan_term.between(*term) & df.income_annum.between(*income)].copy()

def lookup(df, mode='Tất cả', threshold=550, query=''):
    out = df.copy()
    if mode == 'CIBIL thấp nhưng được duyệt':
        out = out.loc[(out.cibil_score < threshold) & out.approved.eq(1)]
    elif mode == 'CIBIL cao nhưng bị từ chối':
        out = out.loc[(out.cibil_score >= threshold) & out.approved.eq(0)]
    elif mode == 'Tài sản cần kiểm tra':
        out = out.loc[out.asset_issue]
    if query.strip():
        # Tìm đúng mã để tránh mã 1 vô tình khớp 10, 100, ...
        ids = [s.strip() for s in query.split(',') if s.strip()]
        out = out.loc[out.loan_id.astype(str).isin(ids)]
    return out

def export_analysis():
    df = load_data()
    dest = ROOT / 'results'
    dest.mkdir(exist_ok=True)
    df.to_csv(dest / 'loan_clean.csv', index=False, encoding='utf-8-sig')
    df.loc[df.asset_issue, ['loan_id', 'residential_assets_value_raw', 'loan_status']].to_csv(
        dest / 'asset_issues.csv', index=False, encoding='utf-8-sig')
    metrics = kpis(df)
    metrics['cibil_by_status'] = df.groupby('loan_status').cibil_score.mean().to_dict()
    metrics['exceptions_low'] = len(lookup(df, 'CIBIL thấp nhưng được duyệt'))
    metrics['exceptions_high'] = len(lookup(df, 'CIBIL cao nhưng bị từ chối'))
    (dest / 'metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')
    for col in ['cibil_band', 'loan_term', 'income_group', 'education', 'self_employed']:
        grouped(df, col).to_csv(dest / f'by_{col}.csv', index=False, encoding='utf-8-sig')
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return df

if __name__ == '__main__':
    export_analysis()
