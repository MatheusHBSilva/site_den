# app.py - Streamlit web app for S-Parameter Plotter

import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import pandas as df  # For potential data handling, but not necessary
import io

# Função para parsear arquivos .s1p, .s2p ou .cal (retorna freq, real, imag)
def parse_s_param(file_content, filename):
    freq = []
    s_real = []
    s_imag = []
    is_s1p = filename.lower().endswith('.s1p') or filename.lower().endswith('.cal')
    
    lines = file_content.decode('utf-8', errors='ignore').splitlines()
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('!'):
            continue
        data = line.split()
        if len(data) < 3:
            continue
        try:
            f_ghz = float(data[0]) / 1e9
            if is_s1p:
                re = float(data[1])
                im = float(data[2])
            else:
                if len(data) < 5:
                    continue
                re = float(data[3])
                im = float(data[4])
            freq.append(f_ghz)
            s_real.append(re)
            s_imag.append(im)
        except (ValueError, IndexError):
            continue
    
    return np.array(freq), np.array(s_real), np.array(s_imag)

# Função para aplicar redução de ruído
def apply_reduction(freq, mag_db, red_freq, red_mag_db):
    if len(red_freq) == 0 or len(red_mag_db) == 0:
        return mag_db
    
    sort_idx = np.argsort(red_freq)
    red_freq = red_freq[sort_idx]
    red_mag_db = red_mag_db[sort_idx]
    
    red_interp = np.interp(freq, red_freq, red_mag_db,
                           left=red_mag_db[0],
                           right=red_mag_db[-1])
    return mag_db - red_interp

# Função para plotar os arquivos selecionados
def plot_files(files_data, titulo, red_freq, red_mag_db, apply_reduction_flags):
    fig, ax = plt.subplots(figsize=(12, 8))
    
    for idx, (filename, file_content) in enumerate(files_data):
        freq, s_real, s_imag = parse_s_param(file_content, filename)
        if len(freq) == 0:
            continue
        
        mag_db = 20 * np.log10(np.sqrt(s_real**2 + s_imag**2 + 1e-12))
        
        if apply_reduction_flags[idx] and red_freq is not None:
            mag_db = apply_reduction(freq, mag_db, red_freq, red_mag_db)
        
        ax.plot(freq, mag_db, label=filename)
    
    ax.set_xlabel('Frequência (GHz)')
    ax.set_ylabel('|S| (dB)')
    ax.set_title(titulo)
    ax.legend(loc='best', ncol=2)
    ax.grid(True)
    
    st.pyplot(fig)

# Função para criar média de dois arquivos
def criar_media(file1_content, file1_name, file2_content, file2_name):
    freq1, re1, im1 = parse_s_param(file1_content, file1_name)
    freq2, re2, im2 = parse_s_param(file2_content, file2_name)
    
    if len(freq1) == 0 or len(freq2) == 0:
        st.error("Um dos arquivos está vazio ou inválido.")
        return None, None
    
    # Usa freq1 como base; interpola o segundo se necessário
    if len(freq1) != len(freq2):
        re2 = np.interp(freq1, freq2, re2)
        im2 = np.interp(freq1, freq2, im2)
    
    re_mean = (re1 + re2) / 2
    im_mean = (im1 + im2) / 2
    freq_mean = freq1
    
    nome_media = f"Média_{file1_name}_{file2_name}.s2p"
    
    # Cria conteúdo do arquivo médio como bytes
    output = io.BytesIO()
    output.write(b"!File created by Averaging App\n")
    output.write(b"# Hz S RI R 50\n")
    for i in range(len(freq_mean)):
        f_hz = freq_mean[i] * 1e9
        line = f"{f_hz} 0 0 {re_mean[i]:.6f} {im_mean[i]:.6f} 0 0 0 0\n".encode()
        output.write(line)
    media_content = output.getvalue()
    
    return nome_media, media_content

# App principal em Streamlit
st.title("Plotter de S-Parameters Web App")

# Upload de arquivos de medição
st.header("Adicionar Arquivos de Medição (.s1p ou .s2p)")
uploaded_files = st.file_uploader("Escolha arquivos .s1p ou .s2p", type=["s1p", "s2p"], accept_multiple_files=True)

if uploaded_files:
    for file in uploaded_files:
        if file.name not in st.session_state.get('files_data', {}):
            if 'files_data' not in st.session_state:
                st.session_state['files_data'] = {}
            st.session_state['files_data'][file.name] = file.read()
            st.session_state['apply_reduction'] = {file.name: False for file in uploaded_files}  # Inicializa checkboxes

# Lista de arquivos adicionados com checkboxes e remover
st.header("Arquivos Adicionados")
if 'files_data' in st.session_state:
    files_to_remove = []
    for filename in list(st.session_state['files_data']):
        col1, col2, col3 = st.columns([3, 1, 1])
        col1.write(filename)
        st.session_state['apply_reduction'][filename] = col2.checkbox("Aplicar redução", value=st.session_state['apply_reduction'].get(filename, False), key=f"apply_{filename}")
        if col3.button("Remover", key=f"remove_{filename}"):
            files_to_remove.append(filename)
    
    for filename in files_to_remove:
        del st.session_state['files_data'][filename]
        del st.session_state['apply_reduction'][filename]

# Upload de arquivo de redução
st.header("Redução de Ruído (opcional)")
red_upload = st.file_uploader("Selecione arquivo de redução (.cal, .s1p, .s2p)", type=["cal", "s1p", "s2p"])

red_freq, red_real, red_imag = None, None, None
red_mag_db = None
if red_upload:
    red_content = red_upload.read()
    red_freq, red_real, red_imag = parse_s_param(red_content, red_upload.name)
    red_mag_db = 20 * np.log10(np.sqrt(red_real**2 + red_imag**2 + 1e-12)) if len(red_freq) > 0 else None

# Criação de média
st.header("Criar Média de 2 Arquivos")
if st.button("Criar Média dos 2 Últimos"):
    if len(st.session_state.get('files_data', {})) >= 2:
        files_list = list(st.session_state['files_data'].keys())
        file1_name = files_list[-2]
        file2_name = files_list[-1]
        file1_content = st.session_state['files_data'][file1_name]
        file2_content = st.session_state['files_data'][file2_name]
        
        nome_media, media_content = criar_media(file1_content, file1_name, file2_content, file2_name)
        if media_content:
            st.session_state['files_data'][nome_media] = media_content
            st.session_state['apply_reduction'][nome_media] = False
            st.success(f"Média criada: {nome_media}")
            
            # Opção de download
            st.download_button(
                label="Baixar Média como .s2p",
                data=media_content,
                file_name=nome_media,
                mime="text/plain"
            )
    else:
        st.warning("Adicione pelo menos 2 arquivos para criar média.")

# Título e gerar gráfico
st.header("Configuração do Gráfico")
titulo = st.text_input("Título do Gráfico", value="Magnitude de S-Parameter")

if st.button("Gerar Gráfico"):
    if 'files_data' in st.session_state and st.session_state['files_data']:
        files_data_list = list(st.session_state['files_data'].items())
        apply_flags = [st.session_state['apply_reduction'][name] for name, _ in files_data_list]
        
        # Verifica se muitos arquivos e agrupa se necessário
        LIMITE = 10
        if len(files_data_list) > LIMITE:
            agrupar = st.radio("Muitos arquivos. Agrupar em múltiplos gráficos?", ("Não", "Sim"))
            if agrupar == "Sim":
                max_por = simpledialog.askinteger("Máximo por gráfico", "Quantos arquivos por gráfico?", initialvalue=10) or 10
                for i in range(0, len(files_data_list), max_por):
                    grupo = files_data_list[i:i + max_por]
                    grupo_flags = apply_flags[i:i + max_por]
                    titulo_grupo = f"{titulo} - Parte {i//max_por + 1}"
                    plot_files(grupo, titulo_grupo, red_freq, red_mag_db, grupo_flags)
                st.stop()
        
        plot_files(files_data_list, titulo, red_freq, red_mag_db, apply_flags)
    else:
        st.warning("Adicione arquivos para gerar o gráfico.")