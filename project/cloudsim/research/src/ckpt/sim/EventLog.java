package ckpt.sim;

import java.io.BufferedWriter;
import java.io.Closeable;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStreamWriter;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.zip.GZIPOutputStream;

/**
 * Structured CSV event logs written while the simulation runs:
 *   checkpoint_events.csv.gz : every COMPLETED checkpoint
 *   failure_events.csv       : every host failure as seen by the broker (incl. lost work)
 *   recovery_events.csv      : replacement ready (after D + B) and restore completed (after R)
 * Times are simulation seconds (0 = 2019-06-01 00:00).
 */
public final class EventLog implements Closeable {
    private final Writer ckpt;
    private final Writer fail;
    private final Writer rec;

    public EventLog(File dir) throws IOException {
        if (!dir.isDirectory() && !dir.mkdirs()) {
            throw new IOException("cannot create " + dir);
        }
        ckpt = new BufferedWriter(new OutputStreamWriter(
                new GZIPOutputStream(new FileOutputStream(new File(dir, "checkpoint_events.csv.gz"))),
                StandardCharsets.UTF_8));
        fail = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(new File(dir, "failure_events.csv")),
                StandardCharsets.UTF_8));
        rec = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(new File(dir, "recovery_events.csv")),
                StandardCharsets.UTF_8));
        ckpt.write("time,stream,serial,job,committed_work_sec,vm,tier\n");
        fail.write("time,stream,serial,job,phase,progress_at_failure_sec,committed_sec,lost_sec,"
                + "interrupted_write_sec,failed_vm,replacement_vm\n");
        rec.write("time,stream,serial,job,event,vm,committed_sec\n");
    }

    private static String f(double v) {
        return String.format(Locale.ROOT, "%.3f", v);
    }

    void checkpoint(double t, int stream, String serial, int job, double committed, int vm, String tier) {
        write(ckpt, f(t) + "," + stream + "," + serial + "," + job + "," + f(committed) + "," + vm + "," + tier);
    }

    void failure(double t, int stream, String serial, int job, String phase, double progress, double committed,
                 double lost, double interruptedWrite, int failedVm, int newVm) {
        write(fail, f(t) + "," + stream + "," + serial + "," + job + "," + phase + "," + f(progress) + ","
                + f(committed) + "," + f(lost) + "," + f(interruptedWrite) + "," + failedVm + "," + newVm);
    }

    void recovery(double t, int stream, String serial, int job, String event, int vm, double committed) {
        write(rec, f(t) + "," + stream + "," + serial + "," + job + "," + event + "," + vm + "," + f(committed));
    }

    private static void write(Writer w, String line) {
        try {
            w.write(line);
            w.write('\n');
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }

    public void close() throws IOException {
        ckpt.close();
        fail.close();
        rec.close();
    }
}
