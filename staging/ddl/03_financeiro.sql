-- Schema financeiro: recebimentos e comissões (4 tabelas).
USE [$(BANCO)];
GO

-- O contrato de recebimento de um orçamento ganho: valor total, quantidade de parcelas e forma
-- de pagamento acordada. Um orçamento pode ter mais de um (aditivo, pedido especial).
IF OBJECT_ID('financeiro.recebimento', 'U') IS NULL
CREATE TABLE financeiro.recebimento (
    id                          bigint          NOT NULL IDENTITY(1,1) CONSTRAINT pk_recebimento PRIMARY KEY,
    orcamento_id                bigint          NOT NULL CONSTRAINT fk_receb_orcamento REFERENCES comercial.orcamento (id),
    dt_emissao                  date            NOT NULL,
    vl_total                    decimal(14,2)   NOT NULL,
    nr_parcelas                 smallint        NOT NULL,
    forma_pagamento_id          smallint        NOT NULL CONSTRAINT fk_receb_forma REFERENCES cadastro.forma_pagamento (id),
    condicao_parcelamento_id    smallint        NULL CONSTRAINT fk_receb_condicao REFERENCES cadastro.condicao_parcelamento (id),
    nm_usuario                  varchar(40)     NOT NULL,
    dt_cancelamento             date            NULL,
    motivo_cancelamento         varchar(200)    NULL,
    dt_atualizacao              datetime2(0)    NOT NULL CONSTRAINT df_receb_atu DEFAULT SYSDATETIME(),
    rv                          rowversion
);
GO

-- As parcelas do recebimento, com vencimento e a marca de pago (o pagamento em si é outra tabela).
IF OBJECT_ID('financeiro.parcela', 'U') IS NULL
CREATE TABLE financeiro.parcela (
    id                  bigint          NOT NULL IDENTITY(1,1) CONSTRAINT pk_parcela PRIMARY KEY,
    recebimento_id      bigint          NOT NULL CONSTRAINT fk_parcela_receb REFERENCES financeiro.recebimento (id),
    nr_parcela          smallint        NOT NULL,
    dt_vencimento       date            NOT NULL,
    vl_parcela          decimal(14,2)   NOT NULL,
    fl_pago             bit             NOT NULL CONSTRAINT df_parcela_pago DEFAULT 0,
    nr_documento        varchar(30)     NULL,
    dt_cancelamento     date            NULL,
    dt_atualizacao      datetime2(0)    NOT NULL CONSTRAINT df_parcela_atu DEFAULT SYSDATETIME(),
    rv                  rowversion,
    CONSTRAINT uq_parcela UNIQUE (recebimento_id, nr_parcela)
);
GO

-- Pagamentos efetivos das parcelas (uma parcela pode ser quitada em mais de um pagamento).
IF OBJECT_ID('financeiro.pagamento', 'U') IS NULL
CREATE TABLE financeiro.pagamento (
    id                  bigint          NOT NULL IDENTITY(1,1) CONSTRAINT pk_pagamento PRIMARY KEY,
    parcela_id          bigint          NOT NULL CONSTRAINT fk_pag_parcela REFERENCES financeiro.parcela (id),
    dt_pagamento        date            NOT NULL,
    vl_pago             decimal(14,2)   NOT NULL,
    vl_juros            decimal(14,2)   NOT NULL CONSTRAINT df_pag_juros DEFAULT 0,
    vl_desconto         decimal(14,2)   NOT NULL CONSTRAINT df_pag_desc DEFAULT 0,
    forma_pagamento_id  smallint        NOT NULL CONSTRAINT fk_pag_forma REFERENCES cadastro.forma_pagamento (id),
    nm_usuario          varchar(40)     NOT NULL,
    dt_atualizacao      datetime2(0)    NOT NULL CONSTRAINT df_pag_atu DEFAULT SYSDATETIME(),
    rv                  rowversion
);
GO

-- Comissões apuradas por orçamento ganho: do vendedor, do parceiro (reserva técnica), do
-- projetista 3D e do supervisor. Cada linha aponta para um usuário OU para um parceiro.
IF OBJECT_ID('financeiro.comissao', 'U') IS NULL
CREATE TABLE financeiro.comissao (
    id              bigint          NOT NULL IDENTITY(1,1) CONSTRAINT pk_comissao PRIMARY KEY,
    orcamento_id    bigint          NOT NULL CONSTRAINT fk_com_orcamento REFERENCES comercial.orcamento (id),
    tipo            varchar(10)     NOT NULL CONSTRAINT ck_com_tipo CHECK (tipo IN ('VENDEDOR', 'PARCEIRO', '3D', 'SUPERVISOR')),
    usuario_id      bigint          NULL CONSTRAINT fk_com_usuario REFERENCES cadastro.usuario (id),
    parceiro_id     bigint          NULL CONSTRAINT fk_com_parceiro REFERENCES cadastro.parceiro (id),
    p_comissao      decimal(5,2)    NOT NULL,
    vl_base         decimal(14,2)   NOT NULL,
    vl_comissao     decimal(14,2)   NOT NULL,
    competencia     char(7)         NOT NULL,
    dt_apuracao     date            NOT NULL,
    dt_pagamento    date            NULL,
    fl_pago         bit             NOT NULL CONSTRAINT df_com_pago DEFAULT 0,
    dt_atualizacao  datetime2(0)    NOT NULL CONSTRAINT df_com_atu DEFAULT SYSDATETIME(),
    rv              rowversion,
    CONSTRAINT ck_com_beneficiario CHECK (
        (usuario_id IS NOT NULL AND parceiro_id IS NULL) OR (usuario_id IS NULL AND parceiro_id IS NOT NULL)
    )
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_com_competencia' AND object_id = OBJECT_ID('financeiro.comissao'))
    CREATE INDEX ix_com_competencia ON financeiro.comissao (competencia, tipo);
GO
