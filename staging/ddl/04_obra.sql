-- Schema obra: a execução do que foi vendido (3 tabelas): medição, instalação e seu histórico.
USE [$(BANCO)];
GO

-- Medição técnica no local (antes da proposta final e, às vezes, remedição depois do ganho).
IF OBJECT_ID('obra.medicao', 'U') IS NULL
CREATE TABLE obra.medicao (
    id              bigint          NOT NULL IDENTITY(1,1) CONSTRAINT pk_medicao PRIMARY KEY,
    orcamento_id    bigint          NOT NULL CONSTRAINT fk_med_orcamento REFERENCES comercial.orcamento (id),
    medidor_id      bigint          NULL CONSTRAINT fk_med_medidor REFERENCES cadastro.usuario (id),
    dt_agendada     datetime2(0)    NOT NULL,
    dt_realizada    datetime2(0)    NULL,
    fl_remedicao    bit             NOT NULL CONSTRAINT df_med_remed DEFAULT 0,
    ds_obs          varchar(300)    NULL,
    dt_atualizacao  datetime2(0)    NOT NULL CONSTRAINT df_med_atu DEFAULT SYSDATETIME(),
    rv              rowversion
);
GO

-- A instalação da obra: previsão, início, fim, problemas e a aprovação do pós-venda.
IF OBJECT_ID('obra.instalacao', 'U') IS NULL
CREATE TABLE obra.instalacao (
    id                      bigint          NOT NULL IDENTITY(1,1) CONSTRAINT pk_instalacao PRIMARY KEY,
    orcamento_id            bigint          NOT NULL CONSTRAINT fk_inst_orcamento REFERENCES comercial.orcamento (id),
    instalador_id           bigint          NULL CONSTRAINT fk_inst_instalador REFERENCES cadastro.usuario (id),
    dt_prevista             date            NOT NULL,
    dt_inicio               date            NULL,
    dt_fim                  date            NULL,
    fl_problema             bit             NOT NULL CONSTRAINT df_inst_problema DEFAULT 0,
    ds_problema             varchar(300)    NULL,
    fl_aprovado_pos_venda   bit             NULL,
    dt_aprovacao_pos_venda  date            NULL,
    dt_atualizacao          datetime2(0)    NOT NULL CONSTRAINT df_inst_atu DEFAULT SYSDATETIME(),
    rv                      rowversion
);
GO

-- Histórico operacional da instalação, por item quando fizer sentido (entrega do fornecedor,
-- montagem, correção, vistoria).
IF OBJECT_ID('obra.instalacao_historico', 'U') IS NULL
CREATE TABLE obra.instalacao_historico (
    id                  bigint          NOT NULL IDENTITY(1,1) CONSTRAINT pk_instalacao_historico PRIMARY KEY,
    instalacao_id       bigint          NOT NULL CONSTRAINT fk_ihist_instalacao REFERENCES obra.instalacao (id),
    orcamento_item_id   bigint          NULL CONSTRAINT fk_ihist_item REFERENCES comercial.orcamento_item (id),
    ds_acao             varchar(300)    NOT NULL,
    dt_acao             datetime2(0)    NOT NULL,
    nm_acao             varchar(40)     NOT NULL,
    dt_atualizacao      datetime2(0)    NOT NULL CONSTRAINT df_ihist_atu DEFAULT SYSDATETIME(),
    rv                  rowversion
);
GO
