-- Schema cadastro: entidades mestres e parametrização (16 tabelas).
USE [$(BANCO)];
GO

-- As unidades físicas da Fictoria (showrooms). A empresa abre unidades ao longo da história.
IF OBJECT_ID('cadastro.unidade', 'U') IS NULL
CREATE TABLE cadastro.unidade (
    id              smallint        NOT NULL CONSTRAINT pk_unidade PRIMARY KEY,
    sigla           varchar(10)     NOT NULL CONSTRAINT uq_unidade_sigla UNIQUE,
    nome            varchar(80)     NOT NULL,
    bairro          varchar(60)     NOT NULL,
    cidade          varchar(60)     NOT NULL,
    uf              char(2)         NOT NULL,
    dt_abertura     date            NOT NULL,
    dt_encerramento date            NULL,
    ativo           bit             NOT NULL CONSTRAINT df_unidade_ativo DEFAULT 1,
    dt_atualizacao  datetime2(0)    NOT NULL CONSTRAINT df_unidade_atu DEFAULT SYSDATETIME(),
    rv              rowversion
);
GO

-- Pessoas que operam o sistema: vendedores, projetistas 3D, medidores, instaladores, gestão.
-- Um usuário pode acumular papéis (flags); o cargo é o papel principal.
IF OBJECT_ID('cadastro.usuario', 'U') IS NULL
CREATE TABLE cadastro.usuario (
    id                  bigint          NOT NULL IDENTITY(1,1) CONSTRAINT pk_usuario PRIMARY KEY,
    login               varchar(40)     NOT NULL CONSTRAINT uq_usuario_login UNIQUE,
    nome                varchar(120)    NOT NULL,
    email               varchar(120)    NULL,
    unidade_id          smallint        NOT NULL CONSTRAINT fk_usuario_unidade REFERENCES cadastro.unidade (id),
    cargo               varchar(20)     NOT NULL CONSTRAINT ck_usuario_cargo CHECK (cargo IN
                            ('VENDEDOR', 'SUPERVISOR', 'PROJETISTA_3D', 'MEDIDOR', 'INSTALADOR', 'GESTOR', 'ADMINISTRATIVO')),
    fl_vendedor         bit             NOT NULL CONSTRAINT df_usuario_vend DEFAULT 0,
    fl_projetista_3d    bit             NOT NULL CONSTRAINT df_usuario_3d DEFAULT 0,
    fl_medidor          bit             NOT NULL CONSTRAINT df_usuario_med DEFAULT 0,
    fl_instalador       bit             NOT NULL CONSTRAINT df_usuario_inst DEFAULT 0,
    dt_admissao         date            NOT NULL,
    dt_desligamento     date            NULL,
    ativo               bit             NOT NULL CONSTRAINT df_usuario_ativo DEFAULT 1,
    dt_atualizacao      datetime2(0)    NOT NULL CONSTRAINT df_usuario_atu DEFAULT SYSDATETIME(),
    rv                  rowversion
);
GO

-- Por onde um orçamento chega. O grupo consolida a leitura "Outras Origens" do negócio:
-- CANAL_PROPRIO (WhatsApp, Instagram, Facebook, SAC/showroom, anúncio), INDICACAO_CLIENTE,
-- ARQUITETOS, CONSTRUTORAS e OUTROS (parceiros irrelevantes ou não identificados).
IF OBJECT_ID('cadastro.origem_contato', 'U') IS NULL
CREATE TABLE cadastro.origem_contato (
    id              smallint        NOT NULL CONSTRAINT pk_origem_contato PRIMARY KEY,
    codigo          varchar(20)     NOT NULL CONSTRAINT uq_origem_codigo UNIQUE,
    nome            varchar(60)     NOT NULL,
    grupo           varchar(20)     NOT NULL CONSTRAINT ck_origem_grupo CHECK (grupo IN
                        ('CANAL_PROPRIO', 'INDICACAO_CLIENTE', 'ARQUITETOS', 'CONSTRUTORAS', 'OUTROS')),
    ativo           bit             NOT NULL CONSTRAINT df_origem_ativo DEFAULT 1,
    dt_atualizacao  datetime2(0)    NOT NULL CONSTRAINT df_origem_atu DEFAULT SYSDATETIME(),
    rv              rowversion
);
GO

-- Parceiros comerciais: sempre pessoa jurídica (escritório de arquitetura ou construtora).
-- Recebem comissão (reserva técnica) sobre os orçamentos que trazem.
IF OBJECT_ID('cadastro.parceiro', 'U') IS NULL
CREATE TABLE cadastro.parceiro (
    id                          bigint          NOT NULL IDENTITY(1,1) CONSTRAINT pk_parceiro PRIMARY KEY,
    tipo                        varchar(15)     NOT NULL CONSTRAINT ck_parceiro_tipo CHECK (tipo IN ('ESCRITORIO', 'CONSTRUTORA')),
    razao_social                varchar(150)    NOT NULL,
    nome_fantasia               varchar(150)    NOT NULL,
    cnpj                        char(14)        NULL,
    contato_nome                varchar(120)    NULL,
    contato_email               varchar(120)    NULL,
    contato_telefone            varchar(20)     NULL,
    bairro                      varchar(60)     NULL,
    cidade                      varchar(60)     NULL,
    uf                          char(2)         NULL,
    p_comissao_padrao           decimal(5,2)    NOT NULL CONSTRAINT df_parceiro_pcom DEFAULT 5.00,
    vendedor_relacionamento_id  bigint          NULL CONSTRAINT fk_parceiro_vendedor REFERENCES cadastro.usuario (id),
    dt_inicio_parceria          date            NOT NULL,
    dt_fim_parceria             date            NULL,
    ativo                       bit             NOT NULL CONSTRAINT df_parceiro_ativo DEFAULT 1,
    dt_atualizacao              datetime2(0)    NOT NULL CONSTRAINT df_parceiro_atu DEFAULT SYSDATETIME(),
    rv                          rowversion
);
GO

-- Clientes (pessoa física na maioria; pessoa jurídica em obras comerciais). Guarda o canal do
-- PRIMEIRO contato e quem indicou (outro cliente ou um parceiro), quando houver.
IF OBJECT_ID('cadastro.cliente', 'U') IS NULL
CREATE TABLE cadastro.cliente (
    id                      bigint          NOT NULL IDENTITY(1,1) CONSTRAINT pk_cliente PRIMARY KEY,
    tipo_pessoa             char(2)         NOT NULL CONSTRAINT ck_cliente_tipo CHECK (tipo_pessoa IN ('PF', 'PJ')),
    nome                    varchar(150)    NOT NULL,
    nome_fantasia           varchar(150)    NULL,
    cpf_cnpj                varchar(14)     NULL,
    email                   varchar(120)    NULL,
    telefone                varchar(20)     NULL,
    dt_nascimento           date            NULL,
    origem_contato_id       smallint        NULL CONSTRAINT fk_cliente_origem REFERENCES cadastro.origem_contato (id),
    cliente_indicador_id    bigint          NULL CONSTRAINT fk_cliente_indicador REFERENCES cadastro.cliente (id),
    parceiro_indicador_id   bigint          NULL CONSTRAINT fk_cliente_parceiro REFERENCES cadastro.parceiro (id),
    unidade_id              smallint        NOT NULL CONSTRAINT fk_cliente_unidade REFERENCES cadastro.unidade (id),
    dt_cadastro             datetime2(0)    NOT NULL,
    nm_cadastro             varchar(40)     NOT NULL,
    ativo                   bit             NOT NULL CONSTRAINT df_cliente_ativo DEFAULT 1,
    dt_atualizacao          datetime2(0)    NOT NULL CONSTRAINT df_cliente_atu DEFAULT SYSDATETIME(),
    rv                      rowversion
);
GO

-- Endereços do cliente: residência, a obra em si, casa de litoral ou de campo, imóvel comercial.
-- Bairro/cidade/UF plausíveis do público-alvo; logradouro, número e CEP sintéticos.
IF OBJECT_ID('cadastro.endereco', 'U') IS NULL
CREATE TABLE cadastro.endereco (
    id              bigint          NOT NULL IDENTITY(1,1) CONSTRAINT pk_endereco PRIMARY KEY,
    cliente_id      bigint          NOT NULL CONSTRAINT fk_endereco_cliente REFERENCES cadastro.cliente (id),
    tipo            varchar(12)     NOT NULL CONSTRAINT ck_endereco_tipo CHECK (tipo IN ('RESIDENCIA', 'OBRA', 'LITORAL', 'CAMPO', 'COMERCIAL')),
    logradouro      varchar(150)    NULL,
    numero          varchar(10)     NULL,
    complemento     varchar(60)     NULL,
    bairro          varchar(60)     NULL,
    cidade          varchar(60)     NOT NULL,
    uf              char(2)         NOT NULL,
    cep             char(8)         NULL,
    fl_principal    bit             NOT NULL CONSTRAINT df_endereco_principal DEFAULT 0,
    dt_atualizacao  datetime2(0)    NOT NULL CONSTRAINT df_endereco_atu DEFAULT SYSDATETIME(),
    rv              rowversion
);
GO

-- Tipos de orçamento. O BI comercial considera apenas VENDA (fl_conta_bi); assistência,
-- garantia e cortesia existem no sistema e precisam ser filtrados (regra de negócio explícita).
IF OBJECT_ID('cadastro.tipo_orcamento', 'U') IS NULL
CREATE TABLE cadastro.tipo_orcamento (
    id              smallint        NOT NULL CONSTRAINT pk_tipo_orcamento PRIMARY KEY,
    nome            varchar(30)     NOT NULL CONSTRAINT uq_tipo_orcamento_nome UNIQUE,
    fl_conta_bi     bit             NOT NULL CONSTRAINT df_tipo_orc_bi DEFAULT 1,
    ativo           bit             NOT NULL CONSTRAINT df_tipo_orc_ativo DEFAULT 1,
    dt_atualizacao  datetime2(0)    NOT NULL CONSTRAINT df_tipo_orc_atu DEFAULT SYSDATETIME(),
    rv              rowversion
);
GO

-- Fases do funil comercial. O grupo é o que o negócio lê: ABERTO, GANHO ou PERDIDO.
IF OBJECT_ID('cadastro.fase', 'U') IS NULL
CREATE TABLE cadastro.fase (
    id              smallint        NOT NULL CONSTRAINT pk_fase PRIMARY KEY,
    nome            varchar(60)     NOT NULL CONSTRAINT uq_fase_nome UNIQUE,
    grupo           varchar(10)     NOT NULL CONSTRAINT ck_fase_grupo CHECK (grupo IN ('ABERTO', 'GANHO', 'PERDIDO')),
    ordem           smallint        NOT NULL,
    ativo           bit             NOT NULL CONSTRAINT df_fase_ativo DEFAULT 1,
    dt_atualizacao  datetime2(0)    NOT NULL CONSTRAINT df_fase_atu DEFAULT SYSDATETIME(),
    rv              rowversion
);
GO

-- Por que um orçamento foi perdido (preço, prazo, concorrência, adiou a obra, sem retorno...).
IF OBJECT_ID('cadastro.motivo_perda', 'U') IS NULL
CREATE TABLE cadastro.motivo_perda (
    id              smallint        NOT NULL CONSTRAINT pk_motivo_perda PRIMARY KEY,
    nome            varchar(60)     NOT NULL CONSTRAINT uq_motivo_perda_nome UNIQUE,
    ativo           bit             NOT NULL CONSTRAINT df_motivo_ativo DEFAULT 1,
    dt_atualizacao  datetime2(0)    NOT NULL CONSTRAINT df_motivo_atu DEFAULT SYSDATETIME(),
    rv              rowversion
);
GO

-- Etapas de execução depois do ganho (medição, projeto/produção, cotação, compras, planejamento,
-- instalação, correção, pós-venda, finalizado), com o prazo-padrão de cada uma em dias.
IF OBJECT_ID('cadastro.status_etapa', 'U') IS NULL
CREATE TABLE cadastro.status_etapa (
    id                  smallint        NOT NULL CONSTRAINT pk_status_etapa PRIMARY KEY,
    nome                varchar(60)     NOT NULL CONSTRAINT uq_status_etapa_nome UNIQUE,
    ordem               smallint        NOT NULL,
    qtd_dias_limite     smallint        NOT NULL,
    fl_pos_venda        bit             NOT NULL CONSTRAINT df_status_posvenda DEFAULT 0,
    ativo               bit             NOT NULL CONSTRAINT df_status_ativo DEFAULT 1,
    dt_atualizacao      datetime2(0)    NOT NULL CONSTRAINT df_status_atu DEFAULT SYSDATETIME(),
    rv                  rowversion
);
GO

-- Ambientes da casa (sala, cozinha, suíte, varanda gourmet, área externa...). Cada item do
-- orçamento pertence a um ambiente.
IF OBJECT_ID('cadastro.ambiente', 'U') IS NULL
CREATE TABLE cadastro.ambiente (
    id              smallint        NOT NULL CONSTRAINT pk_ambiente PRIMARY KEY,
    nome            varchar(60)     NOT NULL CONSTRAINT uq_ambiente_nome UNIQUE,
    dt_atualizacao  datetime2(0)    NOT NULL CONSTRAINT df_ambiente_atu DEFAULT SYSDATETIME(),
    rv              rowversion
);
GO

-- Categorias do catálogo: marcenaria/planejados, revestimentos, louças e metais, cortinas e
-- persianas, proteção solar e pérgolas, reforma (mão de obra), projeto, instalação.
IF OBJECT_ID('cadastro.categoria_item', 'U') IS NULL
CREATE TABLE cadastro.categoria_item (
    id              smallint        NOT NULL CONSTRAINT pk_categoria_item PRIMARY KEY,
    nome            varchar(60)     NOT NULL CONSTRAINT uq_categoria_item_nome UNIQUE,
    fl_servico      bit             NOT NULL CONSTRAINT df_categoria_servico DEFAULT 0,
    dt_atualizacao  datetime2(0)    NOT NULL CONSTRAINT df_categoria_atu DEFAULT SYSDATETIME(),
    rv              rowversion
);
GO

-- Fornecedores dos itens (marcenarias, fábricas de persianas, distribuidores de revestimento...).
IF OBJECT_ID('cadastro.fornecedor', 'U') IS NULL
CREATE TABLE cadastro.fornecedor (
    id                  bigint          NOT NULL IDENTITY(1,1) CONSTRAINT pk_fornecedor PRIMARY KEY,
    razao_social        varchar(150)    NOT NULL,
    nome_fantasia       varchar(150)    NOT NULL,
    cnpj                char(14)        NULL,
    categoria_item_id   smallint        NOT NULL CONSTRAINT fk_fornecedor_categoria REFERENCES cadastro.categoria_item (id),
    cidade              varchar(60)     NULL,
    uf                  char(2)         NULL,
    prazo_entrega_dias  smallint        NOT NULL CONSTRAINT df_fornecedor_prazo DEFAULT 30,
    ativo               bit             NOT NULL CONSTRAINT df_fornecedor_ativo DEFAULT 1,
    dt_atualizacao      datetime2(0)    NOT NULL CONSTRAINT df_fornecedor_atu DEFAULT SYSDATETIME(),
    rv                  rowversion
);
GO

-- Catálogo de produtos e serviços orçáveis, com valor e custo de referência (a margem real
-- nasce da comparação entre o praticado no orçamento e o custo).
IF OBJECT_ID('cadastro.item_catalogo', 'U') IS NULL
CREATE TABLE cadastro.item_catalogo (
    id                      bigint          NOT NULL IDENTITY(1,1) CONSTRAINT pk_item_catalogo PRIMARY KEY,
    codigo                  varchar(20)     NOT NULL CONSTRAINT uq_item_catalogo_codigo UNIQUE,
    descricao               varchar(200)    NOT NULL,
    categoria_item_id       smallint        NOT NULL CONSTRAINT fk_item_categoria REFERENCES cadastro.categoria_item (id),
    fornecedor_id           bigint          NULL CONSTRAINT fk_item_fornecedor REFERENCES cadastro.fornecedor (id),
    unidade_medida          varchar(5)      NOT NULL CONSTRAINT ck_item_um CHECK (unidade_medida IN ('UN', 'M2', 'ML', 'M3', 'H', 'VB')),
    vl_referencia           decimal(14,2)   NOT NULL,
    vl_custo_referencia     decimal(14,2)   NOT NULL,
    fl_gera_comissao        bit             NOT NULL CONSTRAINT df_item_com DEFAULT 1,
    fl_gera_comissao_3d     bit             NOT NULL CONSTRAINT df_item_com3d DEFAULT 0,
    dt_cadastro             datetime2(0)    NOT NULL,
    ativo                   bit             NOT NULL CONSTRAINT df_item_ativo DEFAULT 1,
    dt_atualizacao          datetime2(0)    NOT NULL CONSTRAINT df_item_atu DEFAULT SYSDATETIME(),
    rv                      rowversion
);
GO

-- Formas de pagamento aceitas.
IF OBJECT_ID('cadastro.forma_pagamento', 'U') IS NULL
CREATE TABLE cadastro.forma_pagamento (
    id              smallint        NOT NULL CONSTRAINT pk_forma_pagamento PRIMARY KEY,
    nome            varchar(30)     NOT NULL CONSTRAINT uq_forma_pagamento_nome UNIQUE,
    ativo           bit             NOT NULL CONSTRAINT df_forma_ativo DEFAULT 1,
    dt_atualizacao  datetime2(0)    NOT NULL CONSTRAINT df_forma_atu DEFAULT SYSDATETIME(),
    rv              rowversion
);
GO

-- Condições de parcelamento (entrada + N parcelas a cada X dias).
IF OBJECT_ID('cadastro.condicao_parcelamento', 'U') IS NULL
CREATE TABLE cadastro.condicao_parcelamento (
    id              smallint        NOT NULL CONSTRAINT pk_condicao_parcelamento PRIMARY KEY,
    nome            varchar(40)     NOT NULL CONSTRAINT uq_condicao_nome UNIQUE,
    nr_parcelas     smallint        NOT NULL,
    p_entrada       decimal(5,2)    NOT NULL CONSTRAINT df_condicao_entrada DEFAULT 0,
    intervalo_dias  smallint        NOT NULL CONSTRAINT df_condicao_intervalo DEFAULT 30,
    ativo           bit             NOT NULL CONSTRAINT df_condicao_ativo DEFAULT 1,
    dt_atualizacao  datetime2(0)    NOT NULL CONSTRAINT df_condicao_atu DEFAULT SYSDATETIME(),
    rv              rowversion
);
GO
