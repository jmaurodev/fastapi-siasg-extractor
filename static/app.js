"use strict";

const form = document.getElementById("form-consulta");
const botao = document.getElementById("btn-consultar");
const statusEl = document.getElementById("status");
const areaResultados = document.getElementById("area-resultados");
const contador = document.getElementById("contador");
const corpoTabela = document.getElementById("corpo-tabela");
const filtro = document.getElementById("filtro");

let itensAtuais = [];
let itensVisiveis = [];
let ultimaConsulta = { uasg: "", numero: "", ano: "" };

const COLUNAS = [
  ["numero_item", "Nº do Item"],
  ["tipo_item", "Tipo do Item"],
  ["categoria", "Categoria"],
  ["item", "Item"],
  ["descricao_detalhada", "Descrição Detalhada"],
  ["unidade_fornecimento", "Unidade de Fornecimento"],
];

form.addEventListener("submit", async (evento) => {
  evento.preventDefault();

  const uasg = document.getElementById("uasg").value.trim();
  const numero = document.getElementById("numero").value.trim();
  const ano = document.getElementById("ano").value.trim();
  if (!uasg || !numero || !ano) return;

  ultimaConsulta = { uasg, numero, ano };
  iniciarCarregamento();
  const params = new URLSearchParams({ uasg, numero, ano });

  try {
    const resposta = await fetch(`/pregao/itens?${params}`);
    if (!resposta.ok) {
      const corpo = await resposta.json().catch(() => ({}));
      throw new Error(corpo.detail || `Erro ${resposta.status} ao consultar.`);
    }
    const dados = await resposta.json();
    itensAtuais = dados.itens || [];
    mostrarResultados(itensAtuais);
  } catch (erro) {
    mostrarErro(erro.message || "Falha na consulta.");
  } finally {
    pararCarregamento();
  }
});

filtro.addEventListener("input", () => {
  const termo = filtro.value.toLowerCase();
  itensVisiveis = itensAtuais.filter((item) =>
    [item.categoria, item.item, item.descricao_detalhada, item.unidade_fornecimento]
      .filter(Boolean)
      .some((campo) => campo.toLowerCase().includes(termo))
  );
  renderizarLinhas(itensVisiveis);
  contador.textContent = `${itensVisiveis.length} de ${itensAtuais.length} itens`;
});

document.querySelectorAll(".btn-secundario[data-formato]").forEach((botaoExport) => {
  botaoExport.addEventListener("click", () => exportar(botaoExport.dataset.formato));
});

let cronometro = null;

function iniciarCarregamento() {
  botao.disabled = true;
  areaResultados.hidden = true;
  filtro.value = "";
  const inicio = Date.now();
  const atualizar = () => {
    const seg = Math.floor((Date.now() - inicio) / 1000);
    statusEl.className = "status carregando";
    statusEl.innerHTML = `<span class="spinner"></span>Consultando o comprasnet… (${seg}s) — pode levar alguns segundos.`;
  };
  atualizar();
  cronometro = setInterval(atualizar, 1000);
}

function pararCarregamento() {
  botao.disabled = false;
  if (cronometro) {
    clearInterval(cronometro);
    cronometro = null;
  }
}

function mostrarResultados(itens) {
  if (itens.length === 0) {
    mostrarErro("Nenhum item encontrado para esse pregão.");
    return;
  }
  statusEl.className = "status";
  statusEl.textContent = "";
  areaResultados.hidden = false;
  itensVisiveis = itens;
  contador.textContent = `${itens.length} itens encontrados`;
  renderizarLinhas(itens);
}

function mostrarErro(mensagem) {
  statusEl.className = "status erro";
  statusEl.textContent = mensagem;
  areaResultados.hidden = true;
}

function renderizarLinhas(itens) {
  corpoTabela.replaceChildren();
  const fragmento = document.createDocumentFragment();
  for (const item of itens) {
    const tr = document.createElement("tr");
    adicionarCelula(tr, item.numero_item, "num");
    adicionarCelula(tr, item.tipo_item);
    adicionarCelula(tr, item.categoria, "cat");
    adicionarCelula(tr, item.item);
    adicionarCelula(tr, item.descricao_detalhada);
    adicionarCelula(tr, item.unidade_fornecimento);
    fragmento.appendChild(tr);
  }
  corpoTabela.appendChild(fragmento);
}

function adicionarCelula(tr, valor, classe) {
  const td = document.createElement("td");
  td.textContent = valor ?? "—";
  if (classe) td.className = classe;
  tr.appendChild(td);
}

function exportar(formato) {
  if (itensVisiveis.length === 0) return;
  const geradores = { txt: gerarTxt, csv: gerarCsv, json: gerarJson };
  const tipos = {
    txt: "text/plain;charset=utf-8",
    csv: "text/csv;charset=utf-8",
    json: "application/json;charset=utf-8",
  };
  baixarArquivo(geradores[formato](itensVisiveis), tipos[formato], formato);
}

function gerarJson(itens) {
  return JSON.stringify(itens, null, 2);
}

function gerarCsv(itens) {
  const escapar = (valor) => {
    const texto = valor ?? "";
    return /[";\n]/.test(texto) ? `"${texto.replaceAll('"', '""')}"` : texto;
  };
  const cabecalho = COLUNAS.map(([, titulo]) => titulo).join(";");
  const linhas = itens.map((item) =>
    COLUNAS.map(([chave]) => escapar(item[chave])).join(";")
  );
  // BOM para o Excel pt-BR reconhecer UTF-8 e o separador ";".
  return "﻿" + [cabecalho, ...linhas].join("\r\n");
}

function gerarTxt(itens) {
  return itens
    .map((item) =>
      COLUNAS.map(([chave, titulo]) => `${titulo}: ${item[chave] ?? "—"}`).join("\n")
    )
    .join("\n\n");
}

function baixarArquivo(conteudo, tipo, extensao) {
  const { uasg, numero, ano } = ultimaConsulta;
  const blob = new Blob([conteudo], { type: tipo });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `pregao_${uasg}_${numero}_${ano}.${extensao}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
