-- db_fictoria: modelo relacional do sistema comercial da Fictoria Casa & Interiores
-- (a "produção" simulada, que o staging espelha por carga incremental).
-- Ordem de execução: 00 → 04. Convenções: snake_case, FKs nomeadas, CHECKs para domínios,
-- toda tabela de negócio carrega dt_atualizacao (datetime2) e rv (rowversion): é por elas que
-- a carga incremental do staging enxerga o que mudou desde a última marca d'água, sem varrer
-- a tabela inteira nem pesar na produção.
-- Os scripts são idempotentes (checam existência antes de criar) e rodam via sqlcmd com a
-- variável $(BANCO) informada pelo docker compose: o mesmo DDL cria a origem (db_fictoria) e o
-- staging (stg_fictoria); o staging ganha depois as colunas de controle da carga incremental.

IF DB_ID(N'$(BANCO)') IS NULL
BEGIN
    PRINT 'criando banco $(BANCO)';
    CREATE DATABASE [$(BANCO)] COLLATE Latin1_General_100_CI_AI_SC_UTF8;
END
GO

USE [$(BANCO)];
GO

IF SCHEMA_ID('cadastro')   IS NULL EXEC('CREATE SCHEMA cadastro');
IF SCHEMA_ID('comercial')  IS NULL EXEC('CREATE SCHEMA comercial');
IF SCHEMA_ID('financeiro') IS NULL EXEC('CREATE SCHEMA financeiro');
IF SCHEMA_ID('obra')       IS NULL EXEC('CREATE SCHEMA obra');
GO
