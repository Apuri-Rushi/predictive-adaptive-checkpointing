package ckpt.trace;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.Arrays;
import java.util.List;
import java.util.TreeMap;
import java.util.zip.GZIPInputStream;

import ckpt.policy.RiskTierClassifier;
import ckpt.risk.DailyScoreTimeline;

/**
 * Reads project/ml/results/model_evaluation/test_predictions.csv.gz (read-only) and builds one
 * DailyScoreTimeline per drive of the requested shard.
 *
 * Only three fields are ever extracted from a line: serial_number, date, p_failure_7d_corrected.
 * The label_primary field (outcome information) is NEVER extracted or parsed: fields are cut out
 * by position, and the label position is not among the extracted positions (asserted).
 */
public final class RiskTraceLoader {
    public static final LocalDate DAY0 = LocalDate.of(2019, 6, 1);
    public static final String LABEL_COLUMN = "label_primary";

    public static final class Loaded {
        public final TreeMap<String, DailyScoreTimeline> timelines = new TreeMap<String, DailyScoreTimeline>();
        public final TreeMap<String, Integer> firstDay = new TreeMap<String, Integer>();
        public final TreeMap<String, Integer> scoreCount = new TreeMap<String, Integer>();
        public long rowsRead;
        public long rowsKept;
        public int labelColumnIndex = -1;
        public int[] extractedColumnIndices;
        public List<String> header;
        public int minDay = Integer.MAX_VALUE;
        public int maxDay = Integer.MIN_VALUE;
    }

    private RiskTraceLoader() {
    }

    public static int dayIndex(String isoDate) {
        return (int) ChronoUnit.DAYS.between(DAY0, LocalDate.parse(isoDate));
    }

    public static Loaded load(File gz, int shard, int shards, RiskTierClassifier classifier) throws IOException {
        Loaded out = new Loaded();
        BufferedReader r = new BufferedReader(new InputStreamReader(new GZIPInputStream(new FileInputStream(gz),
                1 << 16), StandardCharsets.UTF_8), 1 << 16);
        try {
            String headerLine = r.readLine();
            out.header = Arrays.asList(headerLine.split(","));
            int iSerial = out.header.indexOf("serial_number");
            int iDate = out.header.indexOf("date");
            int iScore = out.header.indexOf("p_failure_7d_corrected");
            out.labelColumnIndex = out.header.indexOf(LABEL_COLUMN);
            if (iSerial < 0 || iDate < 0 || iScore < 0) {
                throw new IOException("unexpected header: " + headerLine);
            }
            out.extractedColumnIndices = new int[] {iSerial, iDate, iScore};
            for (int i : out.extractedColumnIndices) {
                if (i == out.labelColumnIndex) {
                    throw new IllegalStateException("label column would be extracted");
                }
            }
            int maxIdx = Math.max(iSerial, Math.max(iDate, iScore));
            String[] f = new String[maxIdx + 1];
            String line;
            while ((line = r.readLine()) != null) {
                out.rowsRead++;
                // cut out ONLY the needed positions
                int col = 0, start = 0;
                while (col <= maxIdx) {
                    int comma = line.indexOf(',', start);
                    int end = comma < 0 ? line.length() : comma;
                    if (col == iSerial || col == iDate || col == iScore) {
                        f[col] = line.substring(start, end);
                    }
                    col++;
                    start = end + 1;
                    if (comma < 0) {
                        break;
                    }
                }
                String serial = f[iSerial];
                if (Hashing.shardOf(serial, shards) != shard) {
                    continue;
                }
                int day = dayIndex(f[iDate]);
                double score = Double.parseDouble(f[iScore]);
                DailyScoreTimeline tl = out.timelines.get(serial);
                if (tl == null) {
                    tl = new DailyScoreTimeline(classifier);
                    out.timelines.put(serial, tl);
                    out.firstDay.put(serial, day);
                    out.scoreCount.put(serial, 0);
                }
                tl.addScore(day, score);
                out.firstDay.put(serial, Math.min(out.firstDay.get(serial), day));
                out.scoreCount.put(serial, out.scoreCount.get(serial) + 1);
                out.minDay = Math.min(out.minDay, day);
                out.maxDay = Math.max(out.maxDay, day);
                out.rowsKept++;
            }
        } finally {
            r.close();
        }
        return out;
    }
}
