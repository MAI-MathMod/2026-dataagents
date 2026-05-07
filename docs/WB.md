# World Bank — структура данных

## Структура каталогов

### `codelists/`
SDMX-кодлисты в формате XML.

- `codelists/MA.xml`
  Кодлист Macro Atlas (MA) — классификатор агрегатов и методологий.

- `codelists/SDMX.xml`
  Стандартные кодлисты SDMX — коды статусов наблюдений, типов единиц и т.д.

- `codelists/UNSD.xml`
  Кодлист ООН (UNSD) — стандартные классификации стран и регионов.

- `codelists/WB.xml`
  Кодлист World Bank — собственные классификаторы банка (темы, источники, регионы).

---

SDMX-схемы структур данных.

- `codelists.xml`
  Объединённый файл всех кодлистов в формате SDMX-ML.

- `conceptscheme.xml`
  Схема концептов — описание измерений и атрибутов рядов данных (indicator, country, date, value и др.).

- `datastructure.xml`
  Описание структуры данных (Data Structure Definition, DSD) — связи между концептами и кодлистами.

---

### `parquet/`
Наблюдения по индикаторам в формате Parquet с zstd-сжатием.

- `parquet/{indicator_id}.parquet`
  Один файл на индикатор World Bank. Имя файла соответствует коду индикатора (например `SP.POP.TOTL.parquet`).
  Колонки:
  - `indicator_id` — код индикатора (например `1.0.HCount.1.90usd`)
  - `indicator_name` — название индикатора
  - `country_id` — двухбуквенный код страны/региона
  - `country_name` — название страны или агрегата
  - `countryiso3code` — трёхбуквенный ISO 3166-1 alpha-3 код (может быть `null`)
  - `date` — год наблюдения
  - `value` — числовое значение (может быть `null`)
  - `unit` — единица измерения
  - `obs_status` — статус наблюдения
  - `decimal` — число знаков после запятой

---

Справочники и метаданные (~147 MB).

- `countries.json`
  Список всех стран и регионов World Bank (296 записей).
  Поля: `id`, `iso2Code`, `name`, `region`, `adminregion`, `incomeLevel`, `lendingType`, `capitalCity`, `longitude`, `latitude`.

- `indicators.json`
  Список всех доступных индикаторов (29 470 записей).
  Поля: `id`, `name`, `unit`, `source`, `sourceNote`, `sourceOrganization`, `topics`.

- `dataflows.json`
  SDMX-описание потоков данных (dataflows).
  Структура: `{"resources": [...], "references": [...]}`.
  Каждый ресурс содержит: `id`, `name`, `description`, `agencyID`, `version`, `isFinal`, `urn`, `structure`.

- `inddata.jsonl`
  Агрегированный JSONL-файл с расширенными метаданными по индикаторам (220 строк).
  Каждая строка — JSON-объект с полями: `id`, `IndicatorName`, `Shortdefinition`, `Source`, `Topic`, `name`, `unit`, `source`, `sourceNote` и др.

- `metadata/{source_id}.json`
  Метаданные по источникам данных World Bank (49 файлов, каждый файл — список объектов).
  Имя файла — числовой ID источника (например `reference/metadata/1.json`).
  Поля объекта: `id`, `metatype`, `source_id`.
