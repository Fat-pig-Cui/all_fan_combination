// Offline comparison helper only.  Reads the user-specified JavaScript;
// it does not copy or edit that project and is not used by the Python scorer.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const [coreDirectory, casesPath] = process.argv.slice(2);
if (!coreDirectory || !casesPath) throw new Error('usage: node reference_runner.mjs CORE_DIRECTORY CASES_JSON');
const calcSource = fs.readFileSync(path.join(coreDirectory, 'calcFan.js'), 'utf8');
const constantsSource = fs.readFileSync(path.join(coreDirectory, 'constants.js'), 'utf8');
const utilsSource = fs.readFileSync(path.join(coreDirectory, 'utils.js'), 'utf8');
function topLevelArrow(source, name) {
  const start = source.indexOf(`export const ${name} =`);
  const end = source.indexOf('\n};', start) + 3;
  if (start < 0 || end < start) throw new Error(`Missing ${name} source boundary`);
  return source.slice(start, end).replace('export const', 'const');
}
const split = text => [...text.replace(/\s/g, '').matchAll(/([0-9]+)([mpsz])/g)].flatMap(match => [...match[1]].map(digit => digit + match[2]));
const simple = tile => tile[0] === '0' ? '5' + tile[1] : tile.slice(0, 2);
const constantsClass = constantsSource.slice(0, constantsSource.indexOf('export const DIYFans')).replace('export class Constants', 'class Constants');
const moduleText = constantsClass + '\n' +
  topLevelArrow(utilsSource, 'calcSudian') + '\n' + topLevelArrow(calcSource, 'calcFan') + '\n' +
  calcSource.slice(calcSource.indexOf('const dfs =')) + '\nglobalThis.runFan = calcFan;';
const miscNames = calcSource.match(/import \{([^}]+)\} from "\.\/misc\.js"/)[1].split(',').map(item => item.trim());
const cases = JSON.parse(fs.readFileSync(casesPath, 'utf8'));
const results = [];
for (const input of cases) {
  const seat = Number((input.seat ?? '1z')[0]) - 1;
  const lastName = input.event === 'chankan' ? 'RecordAnGangAddGang' : input.tsumo ? 'RecordDealTile' : 'RecordDiscardTile';
  const playerTiles = Array.from({length: 4}, () => []);
  playerTiles[seat] = [...split(input.hand), input.win];
  const melds = Array.from({length: 4}, () => []);
  melds[seat] = (input.melds ?? []).map(meld => ({type: {chi: 0, pon: 1, minkan: 2, kakan: 2, ankan: 3}[meld.kind], tile: split(meld.tiles)}));
  const liqi = Array.from({length: 4}, () => ({liqi: 0, yifa: 0, kai: false}));
  liqi[seat].liqi = input.riichi ?? 0;
  liqi[seat].yifa = input.ippatsu || input.first_turn ? 1 : 0;
  const context = {
    player_tiles: playerTiles, fulu: melds, liqi_info: liqi, baopai: [[], [], [], []],
    base_info: {player_cnt: 4, ju: 0, chang: Number((input.round_wind ?? '1z')[0]) - 1, lst_draw_type: input.event === 'rinshan' ? 0 : 1},
    dora_cnt: {cnt: 0, li_cnt: 0}, dora_indicator: [[], []],
    paishan: Array(input.event === 'haitei' || input.event === 'houtei' ? 14 : 70).fill('1m'),
    paihe: [[], [], [], []], sigang_bao: {}, yongchang_data: {}, hunzhiyiji_info: {},
    simplify: simple, isEqualTile: (a, b) => simple(a) === simple(b),
    getLstAction: () => ({name: lastName, data: {}}), errRoundInfo: () => '',
    get_fanfu: () => 1, no_leijiyiman: () => false, is_qieshang: () => false,
    judgeTile: (tile, kind) => {
      tile = simple(tile);
      if (kind === 'H') return tile[1] === 'z';
      if (kind === 'T') return tile[1] !== 'z' && (tile[0] === '1' || tile[0] === '9');
      if (kind === 'Y') return tile[1] === 'z' || tile[0] === '1' || tile[0] === '9';
      if (kind === 'D') return tile[1] !== 'z' && tile[0] !== '1' && tile[0] !== '9';
      if (kind === 'L') return ['2s', '3s', '4s', '6s', '8s', '6z'].includes(tile);
      return false;
    },
    calcHupai: tiles => {
      const required = ['1m', '9m', '1p', '9p', '1s', '9s', ...Array.from({length: 7}, (_, i) => (i + 1) + 'z')];
      return tiles.length === 14 && required.every(tile => tiles.some(item => simple(item) === tile)) ? 3 : 0;
    },
  };
  for (const name of miscNames) context[name] = () => false;
  context.get_field_spell_mode = () => 0;
  vm.createContext(context);
  vm.runInContext(moduleText, context, {timeout: 2000});
  context.seatToScore = seat;
  context.tsumoToScore = input.tsumo ?? false;
  results.push(vm.runInContext('runFan(seatToScore, tsumoToScore, (seatToScore + 1) % 4)', context, {timeout: 2000}));
}
process.stdout.write(JSON.stringify(results));
