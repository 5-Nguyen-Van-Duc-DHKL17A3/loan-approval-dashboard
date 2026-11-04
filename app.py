"""Chạy: python -m streamlit run app.py"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from analysis import load_data, kpis, grouped, filter_data, lookup, BANDS

st.set_page_config(page_title='Giám sát phê duyệt tín dụng', layout='wide')
st.markdown('''<style>
.block-container{padding-top:1.6rem;padding-bottom:1.5rem;max-width:1600px}
h1{font-size:2rem!important} h2{font-size:1.3rem!important}
[data-testid="stMetric"]{background:#f5f6f8;padding:16px;border-left:3px solid #263e62;border-radius:4px}
[data-testid="stMetricValue"]{font-size:1.8rem}
</style>''', unsafe_allow_html=True)

@st.cache_data
def source():
    return load_data()

df = source()
COLORS = {'Được duyệt': '#24649a', 'Từ chối': '#c77830'}
PAGES = ['1. Tổng quan', '2. Phân tích chuyên sâu', '3. Tra cứu hồ sơ']
def reset():
    defaults = {'status':['Approved','Rejected'], 'education':['Graduate','Not Graduate'],
        'employed':['Yes','No'], 'score':(300,900), 'term':(2,20), 'income':(.2,9.9),
        'quick':'Tất cả', 'threshold':550, 'query':'', 'sort':'loan_id', 'descending':False}
    for key, value in defaults.items():
        st.session_state[key] = value
def nav(page):
    st.session_state['page'] = page

with st.sidebar:
    st.title('TÍN DỤNG')
    page = st.radio('Trang phân tích', PAGES, key='page')
    st.divider()
    st.subheader('Bộ lọc chung')
    status = st.multiselect('Trạng thái', ['Approved', 'Rejected'],
        default=['Approved', 'Rejected'], key='status',
        format_func=lambda s: {'Approved': 'Được duyệt', 'Rejected': 'Từ chối'}[s])
    education = st.multiselect('Học vấn', ['Graduate', 'Not Graduate'],
        default=['Graduate', 'Not Graduate'], key='education')
    employed = st.multiselect('Tự kinh doanh', ['Yes', 'No'], default=['Yes', 'No'], key='employed')
    score = st.slider('Điểm CIBIL', 300, 900, (300, 900), key='score')
    term = st.slider('Kỳ hạn (đơn vị gốc)', 2, 20, (2, 20), step=2, key='term')
    income = st.slider('Thu nhập năm (triệu đơn vị gốc)', .2, 9.9, (.2, 9.9), step=.1, key='income')
    st.button('Đặt lại bộ lọc', on_click=reset, width='stretch')
    st.caption('Nguồn: Loan Approval Prediction Dataset, Kaggle / Archit Sharma. 4.269 hồ sơ.')

d = filter_data(df, status, education, employed, score, term,
                (round(income[0]*1e6), round(income[1]*1e6)))
st.title('Giám sát hồ sơ phê duyệt tín dụng')
st.caption('Tổng quan quyết định phê duyệt và đặc điểm hồ sơ. Tiền tệ, kỳ hạn hiển thị theo đơn vị gốc chưa xác minh.')
st.markdown(f'**Đang xem {len(d):,} / {len(df):,} hồ sơ** · Bộ lọc chung áp dụng trên cả ba trang.')
if len(d) == 0:
    st.info('Không có hồ sơ phù hợp. Hãy mở rộng hoặc đặt lại bộ lọc.')
    st.stop()

def chart(fig, height=310):
    fig.update_layout(template='plotly_white', height=height,
        margin=dict(l=25, r=20, t=35, b=25), font=dict(family='Arial', size=12),
        legend_title_text='', legend=dict(orientation='h', y=1.14))
    st.plotly_chart(fig, width='stretch', config={'displaylogo': False})

if page == PAGES[0]:
    k = kpis(d)
    cols = st.columns(4)
    for col, name, value, helptext in zip(cols,
        ['Tổng hồ sơ', 'Hồ sơ được duyệt', 'Tỷ lệ phê duyệt', 'Tiền đề nghị vay'],
        [f'{k["total"]:,}', f'{k["approved"]:,}', f'{k["approval_rate"]:.2%}', f'{k["requested_amount"]/1e9:,.2f} tỷ'],
        ['Số dòng sau bộ lọc', 'Số hồ sơ Approved sau bộ lọc',
         'Approved / toàn bộ hồ sơ sau bộ lọc', 'Tổng loan_amount, đơn vị tiền tệ gốc. Không phải giải ngân']):
        col.metric(name, value, help=helptext)
    st.caption('Mẫu số của tỷ lệ là số hồ sơ sau mọi bộ lọc. Chọn riêng một trạng thái sẽ làm tỷ lệ bằng 0% hoặc 100%.')
    a,b = st.columns(2)
    with a:
        st.subheader('Kết quả phê duyệt')
        counts = d.status_vi.value_counts().rename_axis('Trạng thái').reset_index(name='Số hồ sơ')
        chart(px.bar(counts, x='Trạng thái', y='Số hồ sơ', color='Trạng thái',
              color_discrete_map=COLORS, text='Số hồ sơ'))
    with b:
        st.subheader('Phân bố điểm CIBIL')
        chart(px.histogram(d, x='cibil_score', color='status_vi', nbins=30,
              barmode='stack', color_discrete_map=COLORS,
              labels={'cibil_score':'Điểm CIBIL', 'status_vi':'Trạng thái', 'count':'Số hồ sơ'}))
    a,b = st.columns(2)
    with a:
        st.subheader('Tỷ lệ duyệt theo nhóm CIBIL')
        g = grouped(d, 'cibil_band')
        f = px.bar(g, x='cibil_band', y='rate', text=g.rate.map(lambda x:f'{x:.1f}%'),
             custom_data=['total','approved','rejected'], labels={'cibil_band':'Nhóm điểm', 'rate':'Tỷ lệ duyệt (%)'})
        f.update_traces(marker_color='#24649a', hovertemplate='Nhóm %{x}<br>Tỷ lệ %{y:.2f}%<br>Tổng %{customdata[0]}<br>Duyệt %{customdata[1]}<br>Từ chối %{customdata[2]}<extra></extra>')
        f.update_yaxes(range=[0,110]); chart(f)
    with b:
        st.subheader('Phê duyệt theo học vấn và việc làm')
        group = st.selectbox('Chiều so sánh', ['education', 'self_employed'],
                             format_func=lambda x: {'education':'Học vấn', 'self_employed':'Tự kinh doanh'}[x])
        g = grouped(d, group)
        f = go.Figure()
        for label,key in [('Được duyệt','approved'),('Từ chối','rejected')]:
            f.add_bar(x=g[group], y=g[key]/g.total*100, name=label, marker_color=COLORS[label],
                customdata=g[['total',key]], hovertemplate='%{x}<br>%{y:.2f}%<br>Số hồ sơ %{customdata[1]} / %{customdata[0]}<extra></extra>')
        f.update_layout(barmode='stack'); f.update_yaxes(title='Tỷ trọng (%)', range=[0,100]); chart(f)
    st.info(f'Chất lượng dữ liệu trong tập đang xem: {int(d.asset_issue.sum())} hồ sơ có tài sản âm ở nguồn. Giữ hồ sơ và để trống thành phần tài sản không hợp lệ.')
    st.button('Mở phân tích chuyên sâu', on_click=nav, args=(PAGES[1],))

elif page == PAGES[1]:
    st.subheader('Các đặc điểm liên hệ với quyết định phê duyệt')
    a,b = st.columns(2)
    with a:
        st.markdown('**Điểm CIBIL theo kết quả**')
        chart(px.box(d, x='status_vi', y='cibil_score', color='status_vi', points=False,
                     color_discrete_map=COLORS, labels={'status_vi':'Trạng thái','cibil_score':'Điểm CIBIL'}))
    with b:
        st.markdown('**Thu nhập và số tiền đề nghị vay**')
        scatter = d.assign(income_m=d.income_annum/1e6, loan_m=d.loan_amount/1e6)
        f=px.scatter(scatter,x='income_m',y='loan_m',color='status_vi',opacity=.45,
            color_discrete_map=COLORS,hover_data=['loan_id','cibil_score','loan_term'],
            labels={'income_m':'Thu nhập năm (triệu đơn vị gốc)','loan_m':'Khoản vay (triệu đơn vị gốc)','status_vi':'Trạng thái'})
        chart(f)
    a,b = st.columns(2)
    with a:
        st.markdown('**Tỷ lệ duyệt theo CIBIL và kỳ hạn**')
        g=d.groupby(['cibil_band','loan_term'],observed=True).approved.agg(['mean','size'])
        rate=g['mean'].unstack().reindex(BANDS)*100
        sizes=g['size'].unstack().reindex(BANDS)
        f=go.Figure(go.Heatmap(z=rate.to_numpy(),x=[str(x) for x in rate.columns],y=BANDS,
            customdata=sizes.to_numpy(),text=rate.round(1).to_numpy(),texttemplate='%{z:.0f}%',textfont=dict(size=10),
            zmin=0,zmax=100,colorscale='Blues',colorbar=dict(title='%'),
            hovertemplate='CIBIL %{y}<br>Kỳ hạn %{x}<br>Tỷ lệ %{z:.2f}%<br>Số hồ sơ %{customdata}<extra></extra>'))
        f.update_xaxes(title='Kỳ hạn (đơn vị gốc)'); chart(f)
    with b:
        st.markdown('**Tương quan Pearson giữa các biến số**')
        cols=['income_annum','loan_amount','loan_term','cibil_score','loan_income_ratio','approved']
        corr=d[cols].corr()
        names=['Thu nhập','Khoản vay','Kỳ hạn','CIBIL','Vay/thu nhập','Duyệt (0/1)']
        f=go.Figure(go.Heatmap(z=corr.to_numpy(),x=names,y=names,zmin=-1,zmax=1,
            colorscale='RdBu',reversescale=True,text=corr.round(2).to_numpy(),texttemplate='%{text}',
            hovertemplate='%{x} / %{y}<br>r = %{z:.3f}<extra></extra>'))
        chart(f)
    g=grouped(d,'income_group')
    st.markdown('**Đối chiếu phân khúc thu nhập**')
    st.dataframe(g.rename(columns={'income_group':'Tứ phân vị thu nhập','total':'Tổng hồ sơ',
        'approved':'Được duyệt','rate':'Tỷ lệ duyệt (%)','rejected':'Từ chối'}),hide_index=True,width='stretch')
    st.caption('Q1–Q4 được xác định trên toàn bộ nguồn để giữ ngưỡng nhóm ổn định khi lọc. Tương quan không chứng minh quan hệ nhân quả. Vay/thu nhập là số lần, chưa phải DTI. Ô trống là không có dữ liệu hoặc tương quan không xác định.')
    st.button('Mở tra cứu hồ sơ', on_click=nav, args=(PAGES[2],))

else:
    st.subheader('Tra cứu và kiểm tra hồ sơ ngoại lệ')
    a,b,c=st.columns([2,1,2])
    mode=a.selectbox('Lọc nhanh', ['Tất cả','CIBIL thấp nhưng được duyệt',
        'CIBIL cao nhưng bị từ chối','Tài sản cần kiểm tra'],key='quick')
    threshold=b.number_input('Ngưỡng CIBIL phân tích', min_value=300,max_value=900,value=550,step=10,key='threshold')
    query=c.text_input('Mã hồ sơ (ví dụ: 60 hoặc 60,197)',key='query')
    st.caption('Thấp: CIBIL < ngưỡng. Cao: CIBIL ≥ ngưỡng. Đây là quy ước khám phá dữ liệu, không phải quy định phê duyệt hoặc thang xếp hạng tín dụng chính thức.')
    out=lookup(d,mode,threshold,query)
    a,b=st.columns([3,1])
    order=a.selectbox('Sắp xếp theo', ['loan_id','cibil_score','loan_amount','income_annum','loan_income_ratio'],key='sort')
    desc=b.checkbox('Giảm dần',key='descending')
    out=out.sort_values(order,ascending=not desc)
    st.markdown(f'**Kết quả tra cứu: {len(out):,} hồ sơ**')
    show=['loan_id','status_vi','cibil_score','income_annum','loan_amount','loan_term',
          'loan_income_ratio','total_assets','asset_issue','residential_assets_value_raw']
    st.dataframe(out[show], hide_index=True,width='stretch',height=390,
        column_config={'loan_id':'Mã hồ sơ','status_vi':'Kết quả','cibil_score':'CIBIL',
            'income_annum':st.column_config.NumberColumn('Thu nhập năm',format='%d'),
            'loan_amount':st.column_config.NumberColumn('Khoản vay',format='%d'),
            'loan_term':'Kỳ hạn gốc','loan_income_ratio':st.column_config.NumberColumn('Vay/thu nhập (lần)',format='%.2f'),
            'total_assets':'Tổng tài sản hợp lệ','asset_issue':'Cần kiểm tra tài sản',
            'residential_assets_value_raw':'Tài sản nhà ở gốc'})
    st.download_button('Tải CSV kết quả đang lọc',out.to_csv(index=False).encode('utf-8-sig'),
                       'ho_so_dang_loc.csv','text/csv')
    st.caption('Tổng tài sản để trống nếu thiếu ít nhất một thành phần. Cột gốc giữ dấu vết giá trị âm. Tệp CSV chứa đầy đủ các trường dữ liệu sau xử lý.')
    st.button('Về tổng quan',on_click=nav,args=(PAGES[0],))
