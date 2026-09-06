-- Schema comercial: o funil de vendas (7 tabelas). O orçamento é a entidade central do negócio.
USE [$(BANCO)];
GO

-- O orçamento: uma proposta para um cliente, numa unidade, com um vendedor responsável, um canal
-- de entrada e (opcionalmente) um parceiro que o trouxe. Valores totais são o somatório dos
-- itens; comissões nascem do líquido. A fase atual diz se está aberto, ganho ou perdido; a
-- trilha completa de fases vive em orcamento_fase_hist.
IF OBJECT_ID('comercial.orcamento', 'U') IS NULL
CREATE TABLE comercial.orcamento (
    id                              bigint          NOT NULL IDENTITY(1,1) CONSTRAINT pk_orcamento PRIMARY KEY,
    nr_orcamento                    int             NOT NULL CONSTRAINT uq_orcamento_nr UNIQUE,
    unidade_id                      smallint        NOT NULL CONSTRAINT fk_orc_unidade REFERENCES cadastro.unidade (id),
    cliente_id                      bigint          NOT NULL CONSTRAINT fk_orc_cliente REFERENCES cadastro.cliente (id),
    endereco_obra_id                bigint          NULL CONSTRAINT fk_orc_endereco REFERENCES cadastro.endereco (id),
    tipo_orcamento_id               smallint        NOT NULL CONSTRAINT fk_orc_tipo REFERENCES cadastro.tipo_orcamento (id),
    fase_id                         smallint        NOT NULL CONSTRAINT fk_orc_fase REFERENCES cadastro.fase (id),
    origem_contato_id               smallint        NULL CONSTRAINT fk_orc_origem REFERENCES cadastro.origem_contato (id),
    parceiro_id                     bigint          NULL CONSTRAINT fk_orc_parceiro REFERENCES cadastro.parceiro (id),
    vendedor_id                     bigint          NOT NULL CONSTRAINT fk_orc_vendedor REFERENCES cadastro.usuario (id),
    projetista_3d_id                bigint          NULL CONSTRAINT fk_orc_3d REFERENCES cadastro.usuario (id),
    supervisor_id                   bigint          NULL CONSTRAINT fk_orc_supervisor REFERENCES cadastro.usuario (id),
    orcamento_ref_id                bigint          NULL CONSTRAINT fk_orc_ref REFERENCES comercial.orcamento (id),
    ds_objetivo                     varchar(300)    NULL,
    dt_cadastro                     datetime2(0)    NOT NULL,
    nm_cadastro                     varchar(40)     NOT NULL,
    dt_finalizou                    datetime2(0)    NULL,
    nm_finalizou                    varchar(40)     NULL,
    motivo_perda_id                 smallint        NULL CONSTRAINT fk_orc_motivo_perda REFERENCES cadastro.motivo_perda (id),
    dt_cancelou                     datetime2(0)    NULL,
    nm_cancelou                     varchar(40)     NULL,
    vl_total_bruto                  decimal(14,2)   NOT NULL CONSTRAINT df_orc_bruto DEFAULT 0,
    vl_desconto                     decimal(14,2)   NOT NULL CONSTRAINT df_orc_desc DEFAULT 0,
    porc_desconto                   decimal(5,2)    NOT NULL CONSTRAINT df_orc_pdesc DEFAULT 0,
    vl_total_liquido                decimal(14,2)   NOT NULL CONSTRAINT df_orc_liq DEFAULT 0,
    p_comissao_vendedor             decimal(5,2)    NULL,
    vl_comissao_vendedor            decimal(14,2)   NULL,
    p_comissao_parceiro             decimal(5,2)    NULL,
    vl_comissao_parceiro            decimal(14,2)   NULL,
    p_comissao_3d                   decimal(5,2)    NULL,
    vl_comissao_3d                  decimal(14,2)   NULL,
    forma_pagamento_id              smallint        NULL CONSTRAINT fk_orc_forma_pag REFERENCES cadastro.forma_pagamento (id),
    condicao_parcelamento_id        smallint        NULL CONSTRAINT fk_orc_condicao REFERENCES cadastro.condicao_parcelamento (id),
    dt_prazo_entrega                date            NULL,
    fl_pedido_especial              bit             NOT NULL CONSTRAINT df_orc_especial DEFAULT 0,
    fl_garantia                     bit             NOT NULL CONSTRAINT df_orc_garantia DEFAULT 0,
    fl_endereco_entrega_diferente   bit             NOT NULL CONSTRAINT df_orc_end_dif DEFAULT 0,
    dt_atualizacao                  datetime2(0)    NOT NULL CONSTRAINT df_orc_atu DEFAULT SYSDATETIME(),
    rv                              rowversion
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_orc_cliente' AND object_id = OBJECT_ID('comercial.orcamento'))
    CREATE INDEX ix_orc_cliente ON comercial.orcamento (cliente_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_orc_vendedor_dt' AND object_id = OBJECT_ID('comercial.orcamento'))
    CREATE INDEX ix_orc_vendedor_dt ON comercial.orcamento (vendedor_id, dt_cadastro);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_orc_rv' AND object_id = OBJECT_ID('comercial.orcamento'))
    CREATE INDEX ix_orc_rv ON comercial.orcamento (rv);
GO

-- Itens do orçamento: um produto ou serviço do catálogo, num ambiente, com quantidade, valor
-- praticado e custo. É aqui que a margem de verdade mora.
IF OBJECT_ID('comercial.orcamento_item', 'U') IS NULL
CREATE TABLE comercial.orcamento_item (
    id                      bigint          NOT NULL IDENTITY(1,1) CONSTRAINT pk_orcamento_item PRIMARY KEY,
    orcamento_id            bigint          NOT NULL CONSTRAINT fk_item_orcamento REFERENCES comercial.orcamento (id),
    ambiente_id             smallint        NULL CONSTRAINT fk_item_ambiente REFERENCES cadastro.ambiente (id),
    item_catalogo_id        bigint          NOT NULL CONSTRAINT fk_item_catalogo REFERENCES cadastro.item_catalogo (id),
    ds_descricao            varchar(200)    NULL,
    qtd                     decimal(12,3)   NOT NULL,
    vl_unitario             decimal(14,2)   NOT NULL,
    vl_custo                decimal(14,2)   NULL,
    vl_markup               decimal(6,2)    NULL,
    vl_total                decimal(14,2)   NOT NULL,
    ordem                   smallint        NOT NULL,
    dt_cadastro             datetime2(0)    NOT NULL,
    nm_cadastro             varchar(40)     NOT NULL,
    dt_cancelou             datetime2(0)    NULL,
    nm_cancelou             varchar(40)     NULL,
    fl_gera_comissao        bit             NOT NULL CONSTRAINT df_item_gera_com DEFAULT 1,
    dt_liberou_projeto      datetime2(0)    NULL,
    dt_liberou_producao     datetime2(0)    NULL,
    p_instalacao            decimal(5,2)    NULL,
    dt_atualizacao          datetime2(0)    NOT NULL CONSTRAINT df_oitem_atu DEFAULT SYSDATETIME(),
    rv                      rowversion
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_oitem_orcamento' AND object_id = OBJECT_ID('comercial.orcamento_item'))
    CREATE INDEX ix_oitem_orcamento ON comercial.orcamento_item (orcamento_id);
GO

-- Trilha de fases do funil: cada passagem por uma fase registra entrada e saída; a linha com
-- saída em aberto é a fase atual. É o que permite saber quantos orçamentos estavam ABERTOS
-- em qualquer data do passado (o snapshot atual não responde isso).
IF OBJECT_ID('comercial.orcamento_fase_hist', 'U') IS NULL
CREATE TABLE comercial.orcamento_fase_hist (
    id              bigint          NOT NULL IDENTITY(1,1) CONSTRAINT pk_orc_fase_hist PRIMARY KEY,
    orcamento_id    bigint          NOT NULL CONSTRAINT fk_fhist_orcamento REFERENCES comercial.orcamento (id),
    fase_id         smallint        NOT NULL CONSTRAINT fk_fhist_fase REFERENCES cadastro.fase (id),
    dt_entrada      datetime2(0)    NOT NULL,
    dt_saida        datetime2(0)    NULL,
    nm_usuario      varchar(40)     NOT NULL,
    dt_atualizacao  datetime2(0)    NOT NULL CONSTRAINT df_fhist_atu DEFAULT SYSDATETIME(),
    rv              rowversion
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_fhist_orcamento' AND object_id = OBJECT_ID('comercial.orcamento_fase_hist'))
    CREATE INDEX ix_fhist_orcamento ON comercial.orcamento_fase_hist (orcamento_id, dt_entrada);
GO

-- Etapas de execução do orçamento ganho (medição → projeto/produção → ... → finalizado), com
-- prazo-limite e conclusão. A etapa sem conclusão e sem cancelamento é o status operacional atual.
IF OBJECT_ID('comercial.orcamento_etapa', 'U') IS NULL
CREATE TABLE comercial.orcamento_etapa (
    id                  bigint          NOT NULL IDENTITY(1,1) CONSTRAINT pk_orcamento_etapa PRIMARY KEY,
    orcamento_id        bigint          NOT NULL CONSTRAINT fk_etapa_orcamento REFERENCES comercial.orcamento (id),
    status_etapa_id     smallint        NOT NULL CONSTRAINT fk_etapa_status REFERENCES cadastro.status_etapa (id),
    dt_cadastro         datetime2(0)    NOT NULL,
    nm_cadastro         varchar(40)     NOT NULL,
    dt_limite           date            NULL,
    dt_concluiu         datetime2(0)    NULL,
    nm_concluiu         varchar(40)     NULL,
    dt_cancelou         datetime2(0)    NULL,
    nm_cancelou         varchar(40)     NULL,
    fl_manual           bit             NOT NULL CONSTRAINT df_etapa_manual DEFAULT 0,
    fl_concluiu_manual  bit             NOT NULL CONSTRAINT df_etapa_concl_manual DEFAULT 0,
    dt_atualizacao      datetime2(0)    NOT NULL CONSTRAINT df_etapa_atu DEFAULT SYSDATETIME(),
    rv                  rowversion
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_etapa_orcamento' AND object_id = OBJECT_ID('comercial.orcamento_etapa'))
    CREATE INDEX ix_etapa_orcamento ON comercial.orcamento_etapa (orcamento_id, dt_cadastro);
GO

-- Follow-up comercial: cada contato com o cliente (ligação, WhatsApp, visita, reunião) e o
-- próximo contato agendado. Trilha de interação, insumo de análises futuras.
IF OBJECT_ID('comercial.follow_up', 'U') IS NULL
CREATE TABLE comercial.follow_up (
    id                  bigint          NOT NULL IDENTITY(1,1) CONSTRAINT pk_follow_up PRIMARY KEY,
    orcamento_id        bigint          NOT NULL CONSTRAINT fk_fup_orcamento REFERENCES comercial.orcamento (id),
    usuario_id          bigint          NOT NULL CONSTRAINT fk_fup_usuario REFERENCES cadastro.usuario (id),
    dt_lanc             datetime2(0)    NOT NULL,
    tipo_contato        varchar(10)     NOT NULL CONSTRAINT ck_fup_tipo CHECK (tipo_contato IN ('LIGACAO', 'WHATSAPP', 'EMAIL', 'VISITA', 'SHOWROOM', 'REUNIAO')),
    ds_obs              varchar(500)    NULL,
    dt_proximo_contato  date            NULL,
    dt_atualizacao      datetime2(0)    NOT NULL CONSTRAINT df_fup_atu DEFAULT SYSDATETIME(),
    rv                  rowversion
);
GO

-- Histórico textual do orçamento: ações registradas pelo sistema e pelos usuários (versão
-- enviada, desconto aprovado, revisão de itens...). Pouco padronizado, como na vida real.
IF OBJECT_ID('comercial.orcamento_historico', 'U') IS NULL
CREATE TABLE comercial.orcamento_historico (
    id              bigint          NOT NULL IDENTITY(1,1) CONSTRAINT pk_orcamento_historico PRIMARY KEY,
    orcamento_id    bigint          NOT NULL CONSTRAINT fk_hist_orcamento REFERENCES comercial.orcamento (id),
    ds_acao         varchar(300)    NOT NULL,
    dt_acao         datetime2(0)    NOT NULL,
    nm_acao         varchar(40)     NOT NULL,
    fl_log          bit             NOT NULL CONSTRAINT df_hist_log DEFAULT 0,
    dt_atualizacao  datetime2(0)    NOT NULL CONSTRAINT df_hist_atu DEFAULT SYSDATETIME(),
    rv              rowversion
);
GO

-- Auditoria de alterações do orçamento, campo a campo (valor antigo → valor novo, sempre como
-- texto). Conta revisões comerciais: cada mudança de "vl_total_liquido" é uma renegociação.
IF OBJECT_ID('comercial.auditoria_orcamento', 'U') IS NULL
CREATE TABLE comercial.auditoria_orcamento (
    id              bigint          NOT NULL IDENTITY(1,1) CONSTRAINT pk_auditoria_orcamento PRIMARY KEY,
    orcamento_id    bigint          NOT NULL CONSTRAINT fk_aud_orcamento REFERENCES comercial.orcamento (id),
    ds_campo        varchar(60)     NOT NULL,
    vl_antigo       varchar(200)    NULL,
    vl_novo         varchar(200)    NULL,
    nm_alterou      varchar(40)     NOT NULL,
    dt_alterou      datetime2(0)    NOT NULL,
    dt_atualizacao  datetime2(0)    NOT NULL CONSTRAINT df_aud_atu DEFAULT SYSDATETIME(),
    rv              rowversion
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_aud_orcamento' AND object_id = OBJECT_ID('comercial.auditoria_orcamento'))
    CREATE INDEX ix_aud_orcamento ON comercial.auditoria_orcamento (orcamento_id, dt_alterou);
GO
