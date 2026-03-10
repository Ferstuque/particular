import streamlit as st
import requests
import pandas as pd
import plotly.express as px

st.set_page_config(page_title='Dashboard do Streamlit', page_icon=':bar_chart:', layout='wide')

def formata_numero(valor, prefixo = ''):
    for unidade in ['', 'mil']:
        if valor <1000:
            return f'{prefixo} {valor:.2f} {unidade}'
        valor /= 1000
    return f'{prefixo} {valor:.2f} milhões'

st.title('DASHBOARD DE VENDAS 🛒')

# Dados
url = 'https://labdados.com/produtos'
response = requests.get(url)
dados = pd.DataFrame.from_dict(response.json())
dados['Data da Compra'] = pd.to_datetime(dados['Data da Compra'], format='%d/%m/%Y')

# Filtros
st.sidebar.title('Filtros')

# Criar uma lista de anos com a opção de selecionar todos
todos_anos = st.sidebar.checkbox('Todos os anos', value=True)
if todos_anos:
    ano = ''
else:
    ano = st.sidebar.slider('Ano', dados['Data da Compra'].dt.year.min(), dados['Data da Compra'].dt.year.max())

# Filtrar os dados pelo estado selecionado (se não, para "Todos")
if ano != '':
    dados = dados[dados['Data da Compra'].dt.year == ano]

# Criar uma lista de estados para multiseleção de Estados
estados = sorted(dados['Local da compra'].dropna().unique().tolist())
estado_selecionado = st.sidebar.multiselect('Estado', options=estados)

# Filtrar os dados pelo estado selecionado (se não, para "Todos")
if estado_selecionado != []:
    dados = dados[dados['Local da compra'].isin(estado_selecionado)]

# Criar uma lista de para multiseleção de Vendedores
vendedores = sorted(dados['Vendedor'].dropna().unique().tolist())
vendedor_selecionado = st.sidebar.multiselect('Vendedor', options=vendedores)

# Filtrar os dados pelo vendedor selecionado (se não, para "Todos")
if vendedor_selecionado != []:
    dados = dados[dados['Vendedor'].isin(vendedor_selecionado)]

# Tabelas
## Receita
receita_estados = dados.groupby('Local da compra')['Preço'].sum()
receita_estados = dados.drop_duplicates(subset='Local da compra')[['Local da compra', 'lat', 'lon']].merge(receita_estados, left_on='Local da compra', right_index=True). sort_values('Preço', ascending=False)

receita_mensal = dados.set_index('Data da Compra').groupby(pd.Grouper(freq='ME'))['Preço'].sum().reset_index()
receita_mensal['Ano'] = receita_mensal['Data da Compra'].dt.year
receita_mensal['Mês'] = receita_mensal['Data da Compra'].dt.month_name()

dados_categorias = dados.groupby('Categoria do Produto')['Preço'].sum().sort_values(ascending=False)

## Quantidade
quantidade_estados = dados.groupby('Local da compra')['Preço'].count()
quantidade_estados = dados.drop_duplicates(subset='Local da compra')[['Local da compra', 'lat', 'lon']].merge(quantidade_estados, left_on='Local da compra', right_index=True).sort_values('Preço', ascending=False)

quantidade_mensal = dados.set_index('Data da Compra').groupby(pd.Grouper(freq='ME'))['Preço'].count().reset_index()
quantidade_mensal['Ano'] = quantidade_mensal['Data da Compra'].dt.year
quantidade_mensal['Mês'] = quantidade_mensal['Data da Compra'].dt.month_name()

dados_qnt_categorias = dados.groupby('Categoria do Produto')['Preço'].count().sort_values(ascending=False)

## Vendedores
vendedores = pd.DataFrame(dados.groupby('Vendedor')['Preço'].agg(['sum', 'count']))

# Gráficos

## Receita
fig_mapa_receita = px.scatter_geo(
    receita_estados,
    lat='lat',
    lon='lon',
    scope = 'south america',
    size='Preço',
    template = 'seaborn',
    hover_name='Local da compra',
    hover_data={'lat':False, 'lon':False},
    title='Receita por estado'
)

fig_receita_mensal = px.line(
    receita_mensal,
    x='Mês',
    y='Preço',
    markers=True,
    range_y=(0, receita_mensal.max() if not receita_mensal.empty else 0),
    color='Ano',
    line_dash='Ano',
    title='Receita mensal'
)

fig_receita_mensal.update_layout(yaxis_title='Receita')

fig_receita_estados = px.bar(
    receita_estados.head(),
    x='Local da compra',
    y='Preço',
    text_auto=True,
    title='Top estados (receita)'
)

fig_receita_estados.update_layout(yaxis_title='Receita')

fig_receita_categorias = px.bar(
    dados_categorias,
    text_auto=True,
    title='Receita por categoria'
)

fig_receita_categorias.update_layout(yaxis_title='Receita')

## Quantidade
fig_mapa_quantidade = px.scatter_geo(
    quantidade_estados,
    lat='lat',
    lon='lon',
    scope = 'south america',
    size='Preço',
    template = 'seaborn',
    hover_name='Local da compra',
    hover_data={'lat':False, 'lon':False},
    title='Quantidade por estado'
)

fig_quantidade_mensal = px.line(
    quantidade_mensal,
    x='Mês',
    y='Preço',
    markers=True,
    range_y=(quantidade_mensal.min() if not quantidade_mensal.empty else 0, quantidade_mensal['Preço'].max() if not quantidade_mensal.empty else 0),
    color='Ano',
    line_dash='Ano',
    title='Quantidade mensal'
)

fig_quantidade_mensal.update_layout(yaxis_title='Quantidade')

fig_quantidade_estados = px.bar(
    quantidade_estados.head(),
    x='Local da compra',
    y='Preço',
    text_auto=True,
    title='Top estados (quantidade)'
)

fig_quantidade_estados.update_layout(yaxis_title='Quantidade')

# fig_quantidade_categorias = px.bar(
#     dados_qnt_categorias,
#     text_auto=True,
#     title='Quantidade por categoria'
# )

fig_quantidade_categorias = px.bar(
    dados_qnt_categorias.reset_index(name='Quantidade'),
    x='Categoria do Produto',
    y='Quantidade',
    text_auto=True,
    title='Quantidade por categoria'
)


fig_quantidade_categorias.update_layout(yaxis_title='Quantidade')

# Dashboard
aba1, aba2, aba3 = st.tabs(['Receita', 'Quantidade de Vendas', 'Vendedores'])

with aba1:
    coluna1, coluna2 = st.columns(2)
    with coluna1:
        st.metric('Receita', formata_numero(dados['Preço'].sum(), 'R$'))
        st.plotly_chart(fig_mapa_receita, width='content')
        st.plotly_chart(fig_receita_estados, width='content')
    with coluna2:
        st.metric('Quantidade de vendas', formata_numero(dados.shape[0]))
        st.plotly_chart(fig_receita_mensal, width='content')
        st.plotly_chart(fig_receita_categorias, width='content')

with aba2:
    coluna1, coluna2 = st.columns(2)
    with coluna1:
        st.metric('Receita', formata_numero(dados['Preço'].sum(), 'R$'))
        st.plotly_chart(fig_mapa_quantidade, width='stretch')
        st.plotly_chart(fig_quantidade_estados, width='stretch')
    with coluna2:
        st.metric('Quantidade de vendas', formata_numero(dados.shape[0]))
        st.plotly_chart(fig_quantidade_mensal, width='stretch')
        st.plotly_chart(fig_quantidade_categorias, width='stretch')

with aba3:
    qtd_vendedor = st.number_input('Quantidade de vendedores', 2, 10, 5)
    coluna1, coluna2 = st.columns(2)
    with coluna1:
        st.metric('Receita', formata_numero(dados['Preço'].sum(), 'R$'))
        fig_receita_vendedores = px.bar(
        vendedores[['sum']].sort_values('sum', ascending=False).head(qtd_vendedor),
        x='sum',
        y=vendedores[['sum']].sort_values('sum', ascending=False).head(qtd_vendedor).index,
        labels={'sum':'Receita', 'y':'Vendedor'},
        text_auto=True,
        title=f'Top {qtd_vendedor} vendedores (receita)',
        )
        st.plotly_chart(fig_receita_vendedores)
    with coluna2:
        st.metric('Quantidade de vendas', formata_numero(dados.shape[0]))
        fig_vendas_vendedores = px.bar(
        vendedores[['count']].sort_values('count', ascending=False).head(qtd_vendedor),
        x='count',
        y=vendedores[['count']].sort_values('count', ascending=False).head(qtd_vendedor).index,
        labels={'count':'Quantidade', 'y':'Vendedor'},
        text_auto=True,
        title=f'Top {qtd_vendedor} vendedores (quantidade de vendas)',
        )
        st.plotly_chart(fig_vendas_vendedores)
