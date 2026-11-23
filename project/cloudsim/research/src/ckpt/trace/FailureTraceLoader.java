package ckpt.trace;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Set;

/**
 * Reads failure dates from project/ml/results/dataset_audit_revalidation/drive_failure_summary.csv
 * (read-only). Its output is passed ONLY to the FailureInjector (see ExperimentRunner); the broker and
 * the checkpoint policies never receive it.
 *
 * Kept: drives in the simulated pool whose failure date is in June (day 0..29).
 * Failure instant: t_fail = day * 86400 + crc32("fail|" + serial) mod 86400 (identical for all policies).
 */
public final class FailureTraceLoader {

    public static final class TraceFailure {
        public final String serial;
        public final int day;
        public final double time;

        TraceFailure(String serial, int day, double time) {
            this.serial = serial;
            this.day = day;
            this.time = time;
        }
    }

    private FailureTraceLoader() {
    }

    public static double failureTime(String serial, int day) {
        return day * 86400.0 + (Hashing.crc32("fail|" + serial) % 86400L);
    }

    public static List<TraceFailure> load(File csv, Set<String> poolSerials) throws IOException {
        List<TraceFailure> out = new ArrayList<TraceFailure>();
        BufferedReader r = new BufferedReader(new InputStreamReader(new FileInputStream(csv), StandardCharsets.UTF_8));
        try {
            List<String> h = Arrays.asList(r.readLine().split(","));
            int iSerial = h.indexOf("serial_number");
            int iDate = h.indexOf("failure_date");
            if (iSerial < 0 || iDate < 0) {
                throw new IOException("unexpected header " + h);
            }
            String line;
            while ((line = r.readLine()) != null) {
                String[] f = line.split(",", -1);
                String serial = f[iSerial];
                if (!poolSerials.contains(serial)) {
                    continue;
                }
                int day = RiskTraceLoader.dayIndex(f[iDate]);
                if (day < 0 || day > 29) {
                    continue;
                }
                out.add(new TraceFailure(serial, day, failureTime(serial, day)));
            }
        } finally {
            r.close();
        }
        return out;
    }
}
